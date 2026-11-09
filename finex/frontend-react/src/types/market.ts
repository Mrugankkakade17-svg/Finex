export type DataStatus =
  | 'LIVE'
  | 'DELAYED'
  | 'END_OF_DAY'
  | 'CACHED'
  | 'UNAVAILABLE';

export interface MarketSecurity {
  securityId: string;
  symbol: string;
  name: string;
  assetType: string;
  exchange: string;
  currency: string;
}

export interface MarketQuote {
  symbol: string;
  price: number;
  currency: string;
  changeValue: number;
  changePercent: number;
  source: string;
  dataAsOf: string;
  dataStatus: DataStatus;
}

export interface WatchlistItem {
  symbol: string;
  name: string;
  addedAt: string;
}
