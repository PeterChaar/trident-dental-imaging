# Clinic Installation Guide

Step-by-step setup for the dental clinic PC (Windows).

## What you need
- Windows PC (Windows 10 or 11, 64-bit)
- Trident I-View sensor + USB cable
- Trident I-View **TWAIN driver** install disk (or download from trident.dental)
- A USB stick with `TridentDentalImaging` folder (the build output)
- A second USB stick dedicated to **backups** (recommended)

---

## Part 1 — Install the sensor driver (ONCE)

The software cannot talk to the sensor without this.

1. Insert the Trident I-View driver CD, or download the driver.
2. Run `setup.exe` as Administrator.
3. Reboot if prompted.
4. Plug in the sensor's USB.
5. Open **Device Manager** → confirm the sensor appears with **no yellow warning**.

If there's a yellow warning, reinstall the driver. Do not continue until the sensor is recognized.

---

## Part 2 — Install the software

1. Copy the folder `TridentDentalImaging` from the USB stick to `C:\TridentDentalImaging`.
2. Right-click `TridentDentalImaging.exe` → **Send to → Desktop (create shortcut)**.
3. Double-click the desktop shortcut to launch.
4. You'll see the medical disclaimer — click OK.

The program creates `dental_clinic.db` and `image_store\` next to the .exe. **Do not move the .exe out of its folder** — it needs those files.

---

## Part 3 — First-run setup (5 minutes)

Inside the app:

1. **File → Backup & Clinic Settings**
   - Clinic name: *e.g. "Bekaa Valley Dental"*
   - Doctor name: *e.g. "Dr. Khoury"*
   - Backup folder: click **Browse…** and pick the backup USB stick (e.g. `E:\TridentBackups`)
   - Check **"Backup automatically when closing the app"**
   - Keep last **10** backups
   - OK

2. **Patient → New Patient** — add one test patient.

3. **Acquire → From TWAIN Device** — take a test X-ray to confirm the sensor works.
   - If it says *"TWAIN not available"*, install it once:
     - Open **Command Prompt as Administrator**
     - `cd C:\TridentDentalImaging`
     - `python -m pip install twain` *(only if you built from source)*
     - If using the .exe build, `twain` is already bundled.

---

## Part 4 — Daily use

- **Every dentist session** launches the .exe → selects patient → acquires images.
- **When closing the app**, auto-backup runs to the USB stick automatically.
- **Weekly**, take the backup USB stick home or to a safe place. If the clinic PC dies, all patient data is on that USB.

---

## Part 5 — If something breaks

**"Sensor not detected"**
- Check Device Manager. Reinstall the TWAIN driver.

**"Software crashes on startup"**
- Delete `config.json` next to the .exe and relaunch (resets settings).
- DB is safe — it's in `dental_clinic.db`.

**"Lost patient data"**
- File → Restore From Backup → pick the latest `.zip` from the USB stick.
- A safety snapshot of the current DB is kept automatically before restore.

**"Images missing after restore"**
- Backups contain both DB and images. If images aren't showing, check the `image_store\` folder next to the .exe — files should be there.

---

## Building from source (for the developer, not the clinic)

On a **Windows** PC (PyInstaller cannot build Windows .exe from macOS):

```bat
git clone <your repo> trident-dental-imaging
cd trident-dental-imaging
build_windows.bat
```

Output appears in `dist\TridentDentalImaging\`. Copy that entire folder to the clinic PC.

---

## Medical disclaimer — ALWAYS VISIBLE

This software is a **viewing and workflow tool**. It is **NOT a certified medical device**.
For primary diagnostic decisions, the clinician must confirm findings with certified
software and direct clinical examination.
