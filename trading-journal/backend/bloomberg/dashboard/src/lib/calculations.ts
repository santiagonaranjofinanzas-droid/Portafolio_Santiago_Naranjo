export interface Trade {
  id:           string;
  asset:        "QQQ"  "GLD"  "CASH";
  type:         "BUY"  "SELL";
  entry_price:  number;
  shares:       number;
  capital_usd:  number;
  entry_date:   string;
  exit_price:   number  null;
  exit_date:    string  null;
  notes:        string;
  signal_used: {
    regime:       string;
    stress_prob:  number;
    r_narr:       number  null;
    confidence:   number;
  };
}

const mean = (arr: number[]) => arr.reduce((a, b) => a + b, 0) / (arr.length  1);
const std = (arr: number[]) => {
  if(arr.length < 2) return 0;
  const m = mean(arr);
  return Math.sqrt(arr.reduce((sq, n) => sq + Math.pow(n - m, 2), 0) / (arr.length - 1));
};

export const dailyReturns = (navHistory: number[]) => {
  const returns = [];
  for (let i = 1; i < navHistory.length; i++) {
    returns.push((navHistory[i] - navHistory[i - 1]) / navHistory[i - 1]);
  }
  return returns;
};

export const totalReturn = (currentNAV: number, initialCapital: number) =>
  (currentNAV - initialCapital) / initialCapital;

export const currentDrawdown = (nav: number, hwm: number) =>
  (nav - hwm) / hwm;

export const sharpeRatio = (dailyRet: number[], riskFreeRate = 0.0425) => {
  if (dailyRet.length < 2) return 0;
  const annualizedReturn = mean(dailyRet) * 252;
  const annualizedVol    = std(dailyRet) * Math.sqrt(252);
  if (annualizedVol === 0) return 0;
  return (annualizedReturn - riskFreeRate) / annualizedVol;
};

export const portfolioVolatility = (dailyRet: number[]) =>
  std(dailyRet) * Math.sqrt(252);

export const maxDrawdown = (navHistory: number[]) => {
  if (navHistory.length === 0) return 0;
  let maxDD = 0, peak = navHistory[0];
  for (const nav of navHistory) {
    if (nav > peak) peak = nav;
    const dd = (nav - peak) / peak;
    if (dd < maxDD) maxDD = dd;
  }
  return maxDD;
};

export const winRate = (closedTrades: Trade[]) => {
  if (closedTrades.length === 0) return 0;
  const winners = closedTrades.filter(t => t.exit_price !== null && t.exit_price > t.entry_price);
  return winners.length / closedTrades.length;
};
