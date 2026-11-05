import glob, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.kyc import imaging as I, parse as P
t0 = time.time()
for f in sorted(glob.glob("data/kyc_documents/*.png")):
    im = I.load(open(f, "rb").read()); q = I.quality(im)
    if q["skewed"]: im = I.deskew(im, q["skew_degrees"])
    r = P.extract(I.ocr(im)) if not q["blurry"] else {"doc_type": "?", "fields": "BLURRY"}
    print(os.path.basename(f), r["doc_type"], json.dumps(r["fields"], ensure_ascii=False))
print("total", round(time.time() - t0, 1), "s")
