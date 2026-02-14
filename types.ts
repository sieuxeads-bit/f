
export enum ContentType {
  MANGA = 'MANGA',
  ANIME = 'ANIME'
}

export enum Status {
  ONGOING = 'ONGOING',
  COMPLETED = 'COMPLETED',
  HIATUS = 'HIATUS'
}

export interface Chapter {
  id: string;
  number: number;
  title: string;
  pages: string[];
}

export interface ContentItem {
  id: string;
  title: string;
  type: ContentType;
  genre: string[];
  status: Status;
  rating: number;
  episodesOrChapters: number;
  description: string;
  imageUrl: string;
  releaseDate: string;
  chapters?: Chapter[];
}

export interface Advertisement {
  id: string;
  title: string;
  imageUrl: string;
  targetUrl: string;
  position: 'top' | 'middle' | 'sidebar' | 'interstitial';
  active: boolean;
  views: number;
  clicks: number;
  cpc: number; // Cost Per Click
  cpm: number; // Cost Per 1000 Impressions
}

export interface AnalyticsData {
  month: string;
  views: number;
  engagement: number;
  revenue: number;
}
