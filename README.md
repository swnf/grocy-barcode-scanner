# grocy-barcode-scanner

Simple barcode scanner for Grocy with Buzzer feedback. Requires [barcode-server](https://github.com/markusressel/barcode-server) to work.

## Example

Example `docker-compose.yaml` configuration:

```yaml
services:
  barcode-server:
    image: markusressel/barcode-server:latest
    restart: unless-stopped
    environment:
      PUID: "0"
      PGID: "0"
    volumes:
      - ./barcode_server.yaml:/app/barcode_server.yaml:ro
    devices:
      - /dev/input/by-id/my-usb-device-id

  barcode-scanner:
    image: ghcr.io/swnf/grocy-barcode-scanner:1-latest
    restart: unless-stopped
    environment:
      GROCY_URL: "https://grocy.example.com"
      GROCY_API_KEY: "MY_GROCY_API_KEY"
      BARCODE_SERVER_URL: "ws://barcode-server:9654"
      SINGLE_SCAN_ACTION: "CONSUME"
      DOUBLE_SCAN_ACTION: "OPEN"
      BUZZER_PIN: "4"
      MELODY_CONSUME: "X/0.25/-"
      MELODY_OPEN: "X/0.25/-/0.25/X/0.25/-"
      MELODY_FAIL: "X/1/-"
    devices:
      - /dev/gpiomem
```

Example `barcode_server.yaml`:

```yaml
# See https://github.com/markusressel/barcode-server/blob/master/barcode_server.yaml
barcode_server:
  log_level: DEBUG

  server:
    host: "0.0.0.0"
    port: 9654

  drop_event_queue_after: 2m
  retry_interval: 2s

  device_paths:
    - /dev/input/by-id/my-usb-device-id
```

## Environment variables

| Variable                                                  | Description                                                                                                                                                                                                                                                                           |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GROCY_URL`                                               | Base URL of the grocy server                                                                                                                                                                                                                                                          |
| `GROCY_API_KEY` or `GROCY_API_KEY_FILE`                   | Grocy API key                                                                                                                                                                                                                                                                         |
| `BARCODE_SERVER_URL`                                      | Websocket URL of a barcode-server instance. If you use https, this needs to start with `wss://`                                                                                                                                                                                       |
| `BARCODE_SERVER_AUTH_TOKEN`                               | Optional auth token for barcode-server                                                                                                                                                                                                                                                |
| `BARCODE_SERVER_CLIENT_ID`                                | Optional client UUID for barcode-server. If not set, a new one will be generated on each start.                                                                                                                                                                                       |
| `BUZZER_PIN`                                              | Optional buzzer pin. If this is set, the container needs to run on a Raspberry Pi and have access to `/dev/gpiomem`. If not, buzzer feedback is disabled.                                                                                                                             |
| `BUZZER_TYPE`                                             | Either `Buzzer` (the default) or `TonalBuzzer` if you have a buzzer that can play melodies.                                                                                                                                                                                           |
| `MELODY_FAIL`/`MELODY_ADD`/`MELODY_CONSUME`/`MELODY_OPEN` | Buzzer melody that is played. The format is `X for on or - for off/Wait time in seconds/X or -/...`. If you have a `TonalBuzzer` you can use notes like `A4` instead of `X`. MELODY_FAIL (for codes rejected by Grocy) defaults to `X/1/-`. The other ones have to be explicitly set. |
| `SINGLE_SCAN_ACTION`                                      | The action to perform when an item is scanned once (`ADD`/`CONSUME`/`OPEN`).                                                                                                                                                                                                          |
| `DOUBLE_SCAN_ACTION`                                      | Optional action to perform when an item is scanned twice (`ADD`/`CONSUME`/`OPEN`).                                                                                                                                                                                                    |
| `DOUBLE_SCAN_TIMEOUT`                                     | Timestamp to wait for a second scan in seconds. Defaults to `2`.                                                                                                                                                                                                                      |
