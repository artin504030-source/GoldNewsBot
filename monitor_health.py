import json, os, sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
OWNER=os.getenv("GITHUB_OWNER","artin504030-source")
REPO=os.getenv("GITHUB_REPO","GoldNewsBot")
TOKEN=os.getenv("GITHUB_TOKEN","")
BOT_TOKEN=os.getenv("BOT_TOKEN","")
CHAT_ID=os.getenv("CHANNEL_ID","")
STATE_FILE=os.getenv("HEALTH_STATE_FILE","health_state.json")
RULES=[{"workflow":"news.yml","label":"News fetch","max_age_minutes":40},{"workflow":"breaking_news.yml","label":"Breaking monitor","max_age_minutes":20},{"workflow":"telegram_news_commands.yml","label":"Telegram commands","max_age_minutes":20},{"workflow":"daily_digest.yml","label":"Daily report","max_age_minutes":1560}]
def api_get(url, token=TOKEN):
 headers={"Accept":"application/vnd.github+json","User-Agent":"GoldNewsHealthMonitor"}
 if token: headers["Authorization"]=f"Bearer {token}"
 req=Request(url,headers=headers)
 with urlopen(req,timeout=25) as response: return json.loads(response.read().decode())
def check_runs(runs, now=None, max_age_minutes=40):
 now=now or datetime.now(timezone.utc)
 completed=[r for r in runs if r.get("status")=="completed"]
 completed.sort(key=lambda r:r.get("updated_at", ""),reverse=True)
 issues=[]
 if completed and completed[0].get("conclusion")=="failure": issues.append("Latest completed run failed: "+str(completed[0].get("html_url","run link unavailable")))
 successes=[r for r in completed if r.get("conclusion")=="success"]
 if not successes: issues.append("No successful run found in recent history")
 else:
  try: age=(now-datetime.fromisoformat(successes[0]["updated_at"].replace("Z","+00:00"))).total_seconds()/60
  except Exception: age=max_age_minutes+1
  if age>max_age_minutes: issues.append(f"Last successful run is stale ({int(age)} minutes; threshold {max_age_minutes})")
 return issues
def collect_health(api=api_get,rules=RULES):
 report=[]
 for rule in rules:
  url=f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{rule['workflow']}/runs?per_page=10"
  try:
   data=api(url); runs=data.get("workflow_runs",[]) if isinstance(data,dict) else []
   issues=check_runs(runs,max_age_minutes=rule["max_age_minutes"])
   report.append({"label":rule["label"],"issues":issues,"healthy":not issues})
  except Exception as exc: report.append({"label":rule["label"],"issues":["GitHub API check error: "+str(exc)],"healthy":False})
 return report
def load_state(path=STATE_FILE):
 try:
  with open(path,encoding="utf-8") as f: return json.load(f)
 except (FileNotFoundError,json.JSONDecodeError): return {}
def save_state(state,path=STATE_FILE):
 with open(path,"w",encoding="utf-8") as f: json.dump(state,f,ensure_ascii=False,indent=2); f.write("\n")
def compose_transition_messages(report,old_state):
 current={r["label"]:(r["issues"] if not r["healthy"] else []) for r in report}
 new=[]; recovered=[]
 for label,issues in current.items():
  prev=old_state.get(label,[])
  if issues and issues!=prev: new.append((label,issues))
  if not issues and prev: recovered.append(label)
 messages=[]
 if new: messages.append("🚨 Gold News Health Alert\n"+"\n".join("• "+label+": "+"; ".join(issues) for label,issues in new))
 if recovered: messages.append("✅ Gold News Health Recovery\nRecovered: "+", ".join(recovered))
 return current,messages
def send_telegram(message):
 if not BOT_TOKEN or not CHAT_ID: raise RuntimeError("BOT_TOKEN or CHANNEL_ID missing")
 import requests
 response=requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":message},timeout=20)
 response.raise_for_status()
 if not response.json().get("ok"): raise RuntimeError("Telegram API rejected health alert")
def main():
 if not TOKEN: print("Missing GITHUB_TOKEN; cannot query workflow history",file=sys.stderr); return 2
 report=collect_health(); old=load_state(); state,messages=compose_transition_messages(report,old)
 for message in messages:
  if BOT_TOKEN and CHAT_ID: send_telegram(message)
  else: print("Alert (Telegram secrets missing):\n"+message)
 save_state(state)
 for item in report: print(("OK " if item["healthy"] else "WARN ")+item["label"]+(" — "+"; ".join(item["issues"]) if item["issues"] else ""))
 return 0
if __name__=="__main__": sys.exit(main())
