import re
import os

with open("src/optimization.py", "r", encoding="utf-8") as f:
    opt_content = f.read()

dsr_code = """
import scipy.stats as stats

def calcular_probabilistic_sharpe(retornos_portafolio, benchmark_sharpe=0.0):
    mean_ret = retornos_portafolio.mean()
    std_ret = retornos_portafolio.std()
    if std_ret == 0 or len(retornos_portafolio) < 3: 
        return 0.0
    sr = mean_ret / std_ret
    skew = retornos_portafolio.skew()
    kurt = retornos_portafolio.kurtosis() + 3
    n = len(retornos_portafolio)
    
    sr_var = (1 - skew * sr + (kurt - 1) / 4 * sr**2) / (n - 1)
    if sr_var <= 0: return 0.0
    
    psr = stats.norm.cdf((sr - benchmark_sharpe / np.sqrt(252)) / np.sqrt(sr_var))
    return psr

def calcular_deflated_sharpe(retornos_portafolio, trials=8, variance_trials=0.5):
    if trials <= 1:
        trials = 2
    emc = 0.5772156649
    exp_max_sr = np.sqrt(2 * np.log(trials)) + emc / np.sqrt(2 * np.log(trials))
    benchmark_sr_daily = exp_max_sr * np.sqrt(variance_trials) / np.sqrt(252)
    return calcular_probabilistic_sharpe(retornos_portafolio, benchmark_sharpe=benchmark_sr_daily*np.sqrt(252))
"""

if "calcular_probabilistic_sharpe" not in opt_content:
    with open("src/optimization.py", "a", encoding="utf-8") as f:
        f.write(dsr_code)
    print("DSR added to optimization.py")

with open("run_backtest.py", "r", encoding="utf-8") as f:
    rb_content = f.read()

if "from src.optimization import calcular_catsmom_factor" in rb_content:
    rb_content = rb_content.replace(
        "from src.optimization import calcular_catsmom_factor, calcular_floor_causal",
        "from src.optimization import calcular_catsmom_factor, calcular_floor_causal, calcular_deflated_sharpe, calcular_probabilistic_sharpe"
    )

metricas_old = """    return {
        "Sharpe": sharpe,
        "CAGR": cagr,
        "MaxDD": max_dd,
        "Turnover": turnover_diario
    }"""

metricas_new = """    psr = calcular_probabilistic_sharpe(retornos_portafolio)
    dsr = calcular_deflated_sharpe(retornos_portafolio, trials=8)
    return {
        "Sharpe": sharpe,
        "CAGR": cagr,
        "MaxDD": max_dd,
        "Turnover": turnover_diario,
        "PSR": psr,
        "DSR": dsr
    }"""

rb_content = rb_content.replace(metricas_old, metricas_new)

#Fix print statements to include DSR
def replace_print(layer_name, line_search):
    global rb_content
    rb_content = re.sub(
        rf"\ \*\*Capa {layer_name}.*?\ \{{m.*?Turnover\'\]\*100:\.2f\}}% \.*?( Sí  No - \\n)",
        lambda m: m.group(0).replace(" Sí ", f" {{m{layer_name.split(':')[0]}['DSR']:.4f}}  Sí ").replace(" No ", f" {{m{layer_name.split(':')[0]}['DSR']:.4f}}  No ").replace(" - ", f" {{m0['DSR']:.4f}}  - "),
        rb_content
    )

#Since fixing all the formatting is prone to regex errors, I will just do a targeted replace for the console print
rb_content = rb_content.replace(
    " Capa  Sharpe Anualizado  CAGR %  Max Drawdown %  Turnover Diario % ",
    " Capa  Sharpe Anualizado  CAGR %  Max Drawdown %  Turnover Diario %  DSR "
)
rb_content = rb_content.replace(
    " :---  :---:  :---:  :---:  :---: ",
    " :---  :---:  :---:  :---:  :---:  :---: "
)
rb_content = re.sub(r"\ \*\*Capa 0.*?\n", lambda m: m.group(0).replace("\n", "  {m0['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 1.*?\n", lambda m: m.group(0).replace("\n", "  {m1['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 2.*?\n", lambda m: m.group(0).replace("\n", "  {m2['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 3.*?\n", lambda m: m.group(0).replace("\n", "  {m3['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 4.*?\n", lambda m: m.group(0).replace("\n", "  {m4['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 5a.*?\n", lambda m: m.group(0).replace("\n", "  {m5a['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 5b.*?\n", lambda m: m.group(0).replace("\n", "  {m5b['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 5c.*?\n", lambda m: m.group(0).replace("\n", "  {m5c['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 6.*?\n", lambda m: m.group(0).replace("\n", "  {m6['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 7.*?\n", lambda m: m.group(0).replace("\n", "  {m7['DSR']:.4f} \n"), rb_content)
rb_content = re.sub(r"\ \*\*Capa 8.*?\n", lambda m: m.group(0).replace("\n", "  {m8['DSR']:.4f} \n"), rb_content)


with open("run_backtest.py", "w", encoding="utf-8") as f:
    f.write(rb_content)
print("run_backtest.py updated with DSR metrics.")

