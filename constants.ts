
import { ContentItem, ContentType, Status, AnalyticsData, Advertisement, Chapter } from './types';

const generateSamplePages = (count: number, seed: string) => 
  Array.from({ length: count }, (_, i) => `https://picsum.photos/seed/${seed}_${i}/800/1200`);

const sampleChapters: Chapter[] = [
  { id: 'c1', number: 1, title: 'The Beginning', pages: generateSamplePages(5, 'ch1') },
  { id: 'c2', number: 2, title: 'The Encounter', pages: generateSamplePages(5, 'ch2') },
  { id: 'c3', number: 3, title: 'Power Awakens', pages: generateSamplePages(5, 'ch3') },
];

export const INITIAL_DATA: ContentItem[] = [
  {
    id: '1',
    title: 'One Piece',
    type: ContentType.MANGA,
    genre: ['Action', 'Adventure', 'Fantasy'],
    status: Status.ONGOING,
    rating: 9.2,
    episodesOrChapters: 1100,
    description: 'Gold Roger was known as the Pirate King, the strongest and most infamous being to have sailed the Grand Line.',
    imageUrl: 'https://picsum.photos/seed/onepiece/400/600',
    releaseDate: '1997-07-22',
    chapters: sampleChapters
  },
  {
    id: '3',
    title: 'Solo Leveling',
    type: ContentType.MANGA,
    genre: ['Action', 'Adventure', 'Fantasy'],
    status: Status.COMPLETED,
    rating: 8.8,
    episodesOrChapters: 179,
    description: 'In a world where hunters, humans who possess magical abilities, must battle deadly monsters to protect the human race.',
    imageUrl: 'https://picsum.photos/seed/solo/400/600',
    releaseDate: '2018-03-04',
    chapters: sampleChapters
  }
];

export const INITIAL_ADS: Advertisement[] = [
  {
    id: 'ad1',
    title: 'Gaming Gear Sale',
    imageUrl: 'https://picsum.photos/seed/ad1/1200/200',
    targetUrl: 'https://google.com',
    position: 'top',
    active: true,
    views: 1240,
    clicks: 45,
    cpc: 0.5,
    cpm: 2.0
  },
  {
    id: 'ad2',
    title: 'Anime Figure Pre-order',
    imageUrl: 'https://picsum.photos/seed/ad2/800/400',
    targetUrl: 'https://crunchyroll.com',
    position: 'middle',
    active: true,
    views: 850,
    clicks: 120,
    cpc: 0.8,
    cpm: 1.5
  }
];

export const ANALYTICS_DATA: AnalyticsData[] = [
  { month: 'Jan', views: 4000, engagement: 2400, revenue: 450 },
  { month: 'Feb', views: 3000, engagement: 1398, revenue: 380 },
  { month: 'Mar', views: 2000, engagement: 9800, revenue: 920 },
  { month: 'Apr', views: 2780, engagement: 3908, revenue: 510 },
  { month: 'May', views: 1890, engagement: 4800, revenue: 640 },
  { month: 'Jun', views: 2390, engagement: 3800, revenue: 590 },
];
