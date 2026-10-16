"""Copy the Parquet star schema into data/powerbi so it can be committed and
loaded into Power BI without running Python."""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src, dst = root / "output" / "powerbi" / "parquet", root / "data" / "powerbi"
dst.mkdir(parents=True, exist_ok=True)
for p in src.glob("*.parquet"):
    shutil.copy(p, dst / p.name)
    print("copied", p.name)
