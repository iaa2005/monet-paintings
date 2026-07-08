import os, json, cv2

DIR = os.path.expanduser("~/Desktop/paintings")
AVATARS_DIR = os.path.join(DIR, "avatars")
JSON_IN = os.path.join(DIR, "monet_paintings.json")
JSON_OUT = os.path.join(AVATARS_DIR, "avatars.json")
MODEL_PATH = os.path.join(DIR, "python", "models", "face_detection_yunet.onnx")
PADDING = 0.4
MIN_SCORE = 0.5
INPUT_SIZE = 640

FEMALE = ["woman","women","madame","mademoiselle","mme","mlle","camille","jeanne","blanche","suzanne","germaine","alice","girl","lady","mother","maternity","female","dancer","seamstress","embroidering"]
MALE = ["man","men","monsieur","jean","self portrait","self-portrait","andre","victor","leon","pere","paul","poly","michael","boy","male","soldier","fisherman","gardener","woodbearers","dockers","infantry","hunter","gentleman","adolphe","peltier","lauvray","jacquemont","serveau"]


def guess_gender(title):
    t = title.lower()
    for w in FEMALE:
        if w in t: return "female"
    for w in MALE:
        if w in t: return "male"
    return "unknown"


def crop_square(img, x, y, w, h):
    ih, iw = img.shape[:2]
    cx, cy = x + w // 2, y + h // 2
    side = int(max(w, h) * (1 + PADDING) * 3)
    half = side // 2
    x1, y1 = max(0, cx - half), max(0, cy - half)
    x2, y2 = min(iw, x1 + side), min(ih, y1 + side)
    x1, y1 = max(0, x2 - side), max(0, y2 - side)
    crop = img[y1:y2, x1:x2]
    return cv2.resize(crop, (256, 256), interpolation=cv2.INTER_LANCZOS4)


def main():
    os.makedirs(AVATARS_DIR, exist_ok=True)
    detector = cv2.FaceDetectorYN_create(MODEL_PATH, "", (INPUT_SIZE, INPUT_SIZE), score_threshold=MIN_SCORE)

    with open(JSON_IN, "r", encoding="utf-8") as f:
        paintings = json.load(f)

    avatars = []
    total_faces = 0
    pwf = 0

    for i, p in enumerate(paintings):
        fname = p["filename"]
        fpath = os.path.join(DIR, fname)
        if not os.path.exists(fpath):
            continue
        img = cv2.imread(fpath)
        if img is None:
            continue

        h, w = img.shape[:2]
        scale = INPUT_SIZE / max(w, h)
        nw, nh = int(w * scale), int(h * scale)
        rs = cv2.resize(img, (nw, nh))
        sq = cv2.copyMakeBorder(rs, 0, INPUT_SIZE - nh, 0, INPUT_SIZE - nw, cv2.BORDER_CONSTANT)
        detector.setInputSize((INPUT_SIZE, INPUT_SIZE))
        _, faces = detector.detect(sq)
        if faces is None:
            continue

        gender = guess_gender(p.get("title", ""))

        for j, f in enumerate(faces):
            score = float(f[-1])
            if score < MIN_SCORE:
                continue
            fx, fy, fw, fh = int(f[0] / scale), int(f[1] / scale), int(f[2] / scale), int(f[3] / scale)
            avt = crop_square(img, fx, fy, fw, fh)
            aname = f"{os.path.splitext(fname)[0]}_face{j+1}.jpg"
            cv2.imwrite(os.path.join(AVATARS_DIR, aname), avt, [cv2.IMWRITE_JPEG_QUALITY, 92])
            avatars.append({
                "filename": aname,
                "source": fname,
                "gender": gender,
                "title": p.get("title", ""),
                "year": p.get("year", ""),
                "confidence": round(score, 3),
                "bbox": {"x": fx, "y": fy, "w": fw, "h": fh}
            })
            total_faces += 1

        if total_faces > len([a for a in avatars if a['source'] != fname]):
            pwf += 1

        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(paintings)}  faces: {total_faces}")

    pwf = len(set(a["source"] for a in avatars))
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(avatars, f, ensure_ascii=False, indent=2)

    male = sum(1 for a in avatars if a["gender"] == "male")
    female = sum(1 for a in avatars if a["gender"] == "female")
    unknown = sum(1 for a in avatars if a["gender"] == "unknown")
    print(f"\nDone! Paintings with faces: {pwf}, total faces: {total_faces}")
    print(f"Male: {male}, Female: {female}, Unknown: {unknown}")


if __name__ == "__main__":
    main()
