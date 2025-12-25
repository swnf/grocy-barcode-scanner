import asyncio
from websockets.asyncio.client import connect, ClientConnection
from os import environ
from aiohttp import ClientSession
from contextvars import ContextVar
from string import ascii_uppercase
from urllib.parse import quote
from traceback import format_exc
from uuid import uuid4
from json import loads

grocy_url = environ["GROCY_URL"]
if "GROCY_API_KEY_FILE" in environ:
    with open(environ["GROCY_API_KEY_FILE"], "r") as api_key_file:
        api_key = api_key_file.read().strip()
else:
    api_key = environ["GROCY_API_KEY"]
# NOTE: I used to have my own implementation, but had a lot of issues with https://github.com/gvalkov/python-evdev/issues/101
barcode_server_url = environ["BARCODE_SERVER_URL"]
barcode_server_auth_token = environ.get("BARCODE_SERVER_AUTH_TOKEN", None)
barcode_server_client_id = environ.get("BARCODE_SERVER_CLIENT_ID", uuid4())


def action(action_name: str):
    async def handler(barcode: str):
        async with http_session.get().post(
            f"{grocy_url}/api/stock/products/by-barcode/{quote(barcode)}/{action_name}",
            headers={"GROCY-API-KEY": api_key},
            json={"amount": 1},
        ) as response:
            json_response = await response.json()
            print(
                f'{action_name} {barcode} {json_response[0]["product_id"]} {json_response[0]["transaction_id"]}'
            )

    return handler


http_session: ContextVar[ClientSession] = ContextVar("http_session")

GROCY_ACTIONS = {
    "ADD": action("add"),
    "CONSUME": action("consume"),
    "OPEN": action("open"),
}

buzzer_pin = int(environ["BUZZER_PIN"]) if "BUZZER_PIN" in environ else None
buzzer_type = environ.get("BUZZER_TYPE", "Buzzer")

if buzzer_pin is not None:
    from gpiozero import Buzzer, TonalBuzzer
    from gpiozero.tones import Tone

    if buzzer_type == "Buzzer":
        buzzer = Buzzer(buzzer_pin)
    elif buzzer_type == "TonalBuzzer":
        buzzer = TonalBuzzer(buzzer_pin)
    else:
        raise Exception("BUZZER_TYPE needs to be Buzzer or TonalBuzzer")

    def melody(melody: str):
        """
        Returns a function to play the given melody. Example for a melody: "A4/0.5/-/0.5/A4/0.5/-"
        """
        parsed = []
        is_note = True
        for part in melody.split("/"):
            if is_note:
                tone = part
                if buzzer_type == "TonalBuzzer":
                    if tone == "-":
                        tone = None
                    elif tone == "X":
                        tone = Tone.from_note("A4")
                    elif tone[0] in list(ascii_uppercase):
                        # Assume this is a note
                        tone = Tone.from_note(tone)
                    elif "." in tone:
                        # Assume this is a frequency
                        tone = Tone.from_frequency(float(tone))
                    else:
                        # Assume this is a midi note
                        tone = Tone.from_midi(int(tone))
                    # Variable binding is important here!
                    parsed.append(
                        lambda tone=tone: asyncio.sleep(0, result=buzzer.play(tone))
                    )
                elif buzzer_type == "Buzzer":
                    if tone == "X":
                        parsed.append(lambda: asyncio.sleep(0, result=buzzer.on()))
                    elif tone == "-":
                        parsed.append(lambda: asyncio.sleep(0, result=buzzer.off()))
                    else:
                        raise Exception(
                            "A simple buzzer only supports X (on) and - (off)"
                        )
                else:
                    raise Exception("Unexpected buzzer_type")

            else:
                # Variable binding is important here!
                parsed.append(lambda sleep_time=float(part): asyncio.sleep(sleep_time))

            is_note = not is_note

        async def result():
            for entry in parsed:
                await entry()

        return result

    melody_fail = melody(environ.get("MELODY_FAIL", "X/1/-"))

    def wrap_action(original_action, melody_success):
        async def wrapper(barcode: str):
            try:
                await original_action(barcode)
                await melody_success()
            except Exception as e:
                await melody_fail()
                raise

        return wrapper

    for action_name in GROCY_ACTIONS.keys():
        action_setting = f"MELODY_{action_name}"
        if action_setting in environ:
            GROCY_ACTIONS[action_name] = wrap_action(
                GROCY_ACTIONS[action_name], melody(environ[action_setting])
            )

# Needs to be after the buzzer wrapper
single_scan_action = GROCY_ACTIONS[environ["SINGLE_SCAN_ACTION"]]
double_scan_action = (
    GROCY_ACTIONS[environ["DOUBLE_SCAN_ACTION"]]
    if "DOUBLE_SCAN_ACTION" in environ
    else None
)
double_scan_timeout = float(environ.get("DOUBLE_SCAN_TIMEOUT", 2))


async def receive_barcode(barcode_websocket: ClientConnection):
    message = loads(await barcode_websocket.recv(decode=False))
    return message["barcode"]


async def process_barcodes(barcode_websocket: ClientConnection):
    while True:
        # Scan the "first" barcode
        barcode = await receive_barcode(barcode_websocket)
        print(f"First barcode: {barcode}")
        if double_scan_action is None:
            # Always a single scan action
            try:
                await single_scan_action(barcode)
            except:
                print(format_exc())
                print("Failed to process action")
            continue

        while True:
            try:
                async with asyncio.timeout(double_scan_timeout):
                    new_barcode = await receive_barcode(barcode_websocket)
                    print(f"Second barcode: {new_barcode}")

                # We received a second barcode
                if barcode == new_barcode:
                    # Double scan. Process it and continue with "first" barcode
                    try:
                        await double_scan_action(barcode)
                    except:
                        print(format_exc())
                        print("Failed to process action")
                    break
                else:
                    # Different barcode received. Process previous code as single scan and wait for new "second" barcode.
                    try:
                        await single_scan_action(barcode)
                    except:
                        print(format_exc())
                        print("Failed to process action")
                    barcode = new_barcode
            except TimeoutError:
                print("Double scan timeout")
                # No second barcode received. Process previous barcode as single_scan_action.
                try:
                    await single_scan_action(barcode)
                except:
                    print(format_exc())
                    print("Failed to process action")
                break


async def main():
    async with ClientSession(raise_for_status=True) as session, connect(
        barcode_server_url,
        additional_headers={
            "Client-ID": barcode_server_client_id,
            **(
                {}
                if barcode_server_auth_token is None
                else {"X-Auth-Token": barcode_server_auth_token}
            ),
        },
    ) as websocket:
        token = http_session.set(session)
        try:
            await process_barcodes(websocket)
        finally:
            http_session.reset(token)


if __name__ == "__main__":
    asyncio.run(main())
