# Dashboard redesign and device boundaries

## Existing system reviewed

The Flask gateway serves a Vietnamese HTML/CSS/JavaScript dashboard. SQLite stores devices, patients, three slot assignments per box, schedules, medication events, environment readings, commands, alerts, refill verifications, refill sessions, and audit logs. The gateway reads ESP32-S2 telemetry through MQTT in hardware mode; local mode uses software simulators. Admin, nurse, and family access is enforced in `gateway/auth.py`. The existing refill flow is `verify` → `authorize` → device acknowledgment and correct slot opening → `confirm` or `end`. Firmware topic names and payloads remain unchanged.

The previous interface used a stock product photograph, blue dashboard styling, small low-contrast text, and no connection between a selected compartment and the refill form. The redesign uses a neutral canvas, forest actions, clear status colors, larger headings, and a live-data visual model. Existing navigation, charts, history, alerts, commands, simulator controls, pagination, role checks, and refill endpoints remain in place.

## Virtual pill box

`gateway/static/pillbox-model.js` builds a Three.js model from geometry and a locally bundled MIT-licensed Three.js module. The three lids can move independently for **virtual inspection only**. Clicking a lid selects its compartment; the three cards select the same model compartment. The model's LCD texture shows gateway data for the selected slot, schedules, local time, connection state, and the latest barcode lookup result. Model movement never issues a device command or implies a physical lid state. The physical firmware reports opening events, which continue to drive the existing refill confirmation rules.

The pill shapes are visual representations of a compartment interior. Their count, color, and form are not medication inventory or clinical facts; the gateway has no pill count or shape data. If WebGL is unavailable, the compartment cards remain usable. The model renders on interaction and data changes, pauses out of view, responds to reduced-motion settings, and releases its context on destruction.

## Barcode lookup and refill

The scanner uses `BarcodeDetector` with EAN-13, EAN-8, UPC-A, UPC-E, and Code 128 when the browser supports them. Camera access prefers the rear camera and stops when scanning succeeds, the view changes, the page hides, or the user closes it. Manual entry works without a camera. Numeric retail codes are checksum validated. The scanner calls `GET /api/medications/barcodes/<barcode>`; it does **not** call refill verification, authorization, or confirmation.

The additive `medication_barcodes` table stores reviewed barcode-to-medication mappings and optional strength, form, manufacturer, and description fields. It starts empty because the repository contains no approved package barcodes. A Code 128 barcode whose value exactly matches an existing `medication_code` can be found directly in `medication_catalog`. To add a verified retail mapping, an administrator can insert a row after checking the package and the catalog code, for example:

```sql
INSERT INTO medication_barcodes(barcode, medication_code, strength, dosage_form, manufacturer)
VALUES ('4006381333931', 'MED001', NULL, NULL, NULL);
```

The number above is an example of a valid EAN-13 checksum, **not a known mapping for MED001**. Do not insert it into a real database without verifying the package. Unknown codes return 404; no medication facts are inferred. After a successful lookup the user can copy the catalog medication code into the existing refill form, review it, then explicitly verify and authorize using the original backend flow.

## Physical LCD/OLED integration

The follow-up implementation now includes SSD1306 OLED wiring and a firmware driver, plus keypad/UART barcode capture. See [product-controls.md](product-controls.md) for pins, behavior, dependencies, and physical-device limits. The hardware OLED displays RTC time and firmware schedule codes; the dashboard screen displays gateway assignments. Gateway medication names are not yet sent back to the physical OLED.

## Known limits

- There is no pill inventory sensor, refill level sensor, or lid-position sensor. The dashboard cannot truthfully show pill counts, refill levels, or a real-time physical lid angle.
- Retail barcodes identify a catalog entry only after an approved mapping is entered. No external medication service is configured, and no dosage is inferred from a barcode.
- Browser camera scanning requires HTTPS or localhost and a browser with `BarcodeDetector`; manual code entry remains available elsewhere.
