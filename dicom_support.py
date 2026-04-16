"""DICOM import/export support for dental X-rays."""

import numpy as np

try:
    import pydicom
    from pydicom.dataset import FileDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid
    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False


def can_use_dicom():
    return HAS_PYDICOM


def load_dicom(path):
    if not HAS_PYDICOM:
        raise RuntimeError("pydicom not installed")
    ds = pydicom.dcmread(path)
    arr = ds.pixel_array.astype(np.float64)
    pmin, pmax = arr.min(), arr.max()
    if pmax > pmin:
        arr = ((arr - pmin) / (pmax - pmin) * 255).astype(np.uint8)
    else:
        arr = arr.astype(np.uint8)
    if hasattr(ds, "PhotometricInterpretation") and ds.PhotometricInterpretation == "MONOCHROME1":
        arr = 255 - arr

    meta = {}
    for tag in ["PatientName", "PatientID", "PatientBirthDate",
                "StudyDate", "Modality", "Manufacturer",
                "InstitutionName", "StudyDescription",
                "Rows", "Columns", "BitsAllocated", "BitsStored"]:
        if hasattr(ds, tag):
            meta[tag] = str(getattr(ds, tag))

    if hasattr(ds, "PixelSpacing"):
        ps = ds.PixelSpacing
        meta["pixel_spacing_mm"] = (float(ps[0]), float(ps[1]))
    elif hasattr(ds, "ImagerPixelSpacing"):
        ps = ds.ImagerPixelSpacing
        meta["pixel_spacing_mm"] = (float(ps[0]), float(ps[1]))

    return arr, meta


def save_dicom(path, arr, patient_name="", patient_id="",
               study_description="Dental Intraoral", pixel_spacing=None):
    if not HAS_PYDICOM:
        raise RuntimeError("pydicom not installed")
    import cv2
    if len(arr.shape) == 3:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    arr = arr.astype(np.uint16)

    fm = pydicom.Dataset()
    fm.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1.1"
    fm.MediaStorageSOPInstanceUID = generate_uid()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(path, {}, file_meta=fm, preamble=b"\x00" * 128)
    ds.SOPClassUID = fm.MediaStorageSOPClassUID
    ds.SOPInstanceUID = fm.MediaStorageSOPInstanceUID
    ds.PatientName = patient_name
    ds.PatientID = patient_id
    ds.Modality = "IO"
    ds.Manufacturer = "Trident Dental Imaging"
    ds.StudyDescription = study_description
    ds.SeriesDescription = "Intraoral"
    ds.Rows, ds.Columns = arr.shape
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    ds.PixelData = arr.tobytes()
    if pixel_spacing:
        ds.PixelSpacing = [str(pixel_spacing[0]), str(pixel_spacing[1])]
    ds.save_as(path)


def info_text(meta):
    lines = []
    names = {"PatientName": "Patient", "PatientID": "ID", "StudyDate": "Study Date",
             "Modality": "Modality", "Manufacturer": "Mfr", "Rows": "Height",
             "Columns": "Width", "BitsStored": "Bits"}
    for k, v in meta.items():
        if k == "pixel_spacing_mm":
            lines.append(f"Pixel Spacing: {v[0]:.4f} x {v[1]:.4f} mm")
        else:
            lines.append(f"{names.get(k, k)}: {v}")
    return "\n".join(lines)
