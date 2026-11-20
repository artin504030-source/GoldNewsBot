"""Cross-market event impact mapping (heuristic, explanatory; not trading advice)."""
import re
EVENT_GROUPS={
 'central_bank':(['central bank','fed','fomc','ecb','boe','boj','rba','rbnz','rate decision','interest rate','monetary policy'],['USD','EUR','GBP','JPY','AUD','NZD','XAUUSD','DXY'],['FX','Gold','Equity indices','Bond yields']),
 'inflation':(['cpi','core cpi','pce','inflation','price pressures'],['USD','EUR','GBP','JPY','XAUUSD','DXY','US30','NAS100','US500'],['FX','Gold','Equity indices','Bond yields']),
 'employment':(['nfp','nonfarm','non-farm','payroll','unemployment','jobless','employment'],['USD','XAUUSD','DXY','US30','NAS100','US500'],['FX','Gold','Equity indices','Bond yields']),
 'growth':(['gdp','growth','recession','economic activity','pmi','ism'],['USD','EUR','GBP','AUD','NZD','US30','NAS100','US500','GER40','XAUUSD'],['FX','Equity indices','Gold']),
 'risk_geopolitical':(['war','conflict','strike','sanction','tariff','geopolitical','ceasefire','invasion'],['XAUUSD','USOIL','UKOIL','DXY','US30','NAS100','US500','VIX'],['Gold','Oil','Dollar','Equity indices','Volatility']),
 'energy':(['oil','crude','opec','natural gas','energy'],['USOIL','UKOIL','NATGAS','CAD','XAUUSD','US30','US500'],['Energy','CAD','Gold','Equity indices']),
 'crypto':(['bitcoin','btc','ethereum','crypto','digital asset'],['BTCUSD','ETHUSD','DXY','NAS100','VIX'],['Crypto','Dollar','Tech equities','Volatility']),
 'china':(['china','chinese','pboc','yuan','beijing'],['CNY','AUD','NZD','USOIL','XAUUSD','US30','US500'],['China-sensitive FX','Commodities','Gold','Equity indices']),
}
DIRECT_MARKETS={'central_bank':['currencies named in headline / decision country'],'inflation':['country currency','gold','bond yields'],'employment':['USD and local currency','gold','equity indices'],'growth':['local currency','equity indices','commodities'],'risk_geopolitical':['gold','oil if supply affected','dollar','equity indices','volatility'],'energy':['oil/gas contracts','CAD','energy-linked equities'],'crypto':['BTC/ETH','risk-sensitive equities','USD'],'china':['CNY','AUD/NZD','commodities']}
SYMBOLS_BY_CURRENCY={'USD':['DXY','XAUUSD','US30','NAS100','US500'],'EUR':['EURUSD','GER40'],'GBP':['GBPUSD','UK100'],'JPY':['USDJPY','JP225'],'AUD':['AUDUSD'],'NZD':['NZDUSD'],'CAD':['USDCAD','USOIL'],'CHF':['USDCHF'],'CNY':['CNY','AUDUSD','USOIL']}

def classify_event(text):
 t=(text or '').lower(); groups=[]
 for group,(keywords,_,__) in EVENT_GROUPS.items():
  if any(k in t for k in keywords): groups.append(group)
 return groups

def analyze_cross_market_impact(title, summary='', currency=None, country=None):
 text=(str(title or '')+' '+str(summary or '')).lower(); groups=classify_event(text)
 symbols=set(); markets=set(); rationale=[]
 for g in groups:
  _,syms,mks=EVENT_GROUPS[g]; symbols.update(syms); markets.update(mks); rationale.append(g)
 cur=(currency or '').upper()
 if not cur and country:
  cc={'US':'USD','UNITED STATES':'USD','USA':'USD','EU':'EUR','EUROZONE':'EUR','UK':'GBP','UNITED KINGDOM':'GBP','JAPAN':'JPY','CANADA':'CAD','AUSTRALIA':'AUD','NEW ZEALAND':'NZD','SWITZERLAND':'CHF','CHINA':'CNY'}
  cur=cc.get(str(country).upper(),'')
 if cur in SYMBOLS_BY_CURRENCY: symbols.update(SYMBOLS_BY_CURRENCY[cur])
 symbols=sorted(symbols)
 direct=[]; indirect=[]
 for g in groups:
  direct.extend(DIRECT_MARKETS[g])
 indirect=[m for m in sorted(markets) if m not in direct]
 if not groups:
  return {'categories':[],'currency':cur or None,'symbols':symbols,'direct_effect':[],'indirect_effect':[],'direction':'نامشخص','confidence':'کم','note':'دسته خبر مشخص نشد؛ اثر جهت‌دار ساخته نشد.'}
 return {'categories':groups,'currency':cur or None,'symbols':symbols,'direct_effect':list(dict.fromkeys(direct)),'indirect_effect':indirect,'direction':'بدون جهت قیمت؛ فقط نقشه ارتباط بازار','confidence':'پایین تا متوسط (قواعد کلیدواژه‌ای)','note':'این نقشه روابط احتمالی را نشان می‌دهد؛ اثر واقعی به داده، انتظارات، وضعیت بازار و متن کامل خبر وابسته است.'}
