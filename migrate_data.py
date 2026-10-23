"""Copy old local accounts/media to this NEW project without overwriting either."""
import argparse,shutil,sqlite3
from pathlib import Path
p=argparse.ArgumentParser(description='Stop both BankShield servers before migrating.');p.add_argument('old_instance',type=Path);a=p.parse_args()
src=a.old_instance.resolve();dst=Path(__file__).resolve().parent/'instance'
if not (src/'bankshield.db').exists():raise SystemExit('The source must be the old instance folder containing bankshield.db.')
if src==dst:raise SystemExit('Source and destination must differ.')
if dst.exists() and any(dst.iterdir()):raise SystemExit('Destination instance folder is not empty. Use a fresh extracted project folder; nothing was overwritten.')
dst.mkdir(exist_ok=True)
with sqlite3.connect(src/'bankshield.db') as old,sqlite3.connect(dst/'bankshield.db') as new:old.backup(new)
if (src/'media').exists():shutil.copytree(src/'media',dst/'media')
if (src/'secret.key').exists():shutil.copy2(src/'secret.key',dst/'secret.key')
print('Copied accounts, approved profiles, application history and media. Original data remain unchanged.')
print('Start app.py. Database columns migrate automatically. Pending older applications can be reanalyzed by the admin.')
