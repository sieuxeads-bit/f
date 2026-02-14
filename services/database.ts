
import { ContentItem, Advertisement } from '../types';

// Lưu ý: Để chạy thật, bạn cần điền thông tin từ Supabase của bạn
// Nếu không có, hệ thống sẽ tự động dùng LocalStorage như một phương án dự phòng (Fallback)
const CLOUD_CONFIG = {
  url: (process.env.SUPABASE_URL as string) || '',
  key: (process.env.SUPABASE_ANON_KEY as string) || ''
};

const isCloudEnabled = () => CLOUD_CONFIG.url && CLOUD_CONFIG.key;

export const dbService = {
  // Lấy toàn bộ danh sách truyện từ Cloud
  fetchItems: async (fallbackData: ContentItem[]): Promise<ContentItem[]> => {
    if (!isCloudEnabled()) {
      console.warn("Database Cloud chưa cấu hình. Đang dùng dữ liệu nội bộ.");
      const saved = localStorage.getItem('manganexus_data');
      return saved ? JSON.parse(saved) : fallbackData;
    }

    try {
      const response = await fetch(`${CLOUD_CONFIG.url}/rest/v1/manga_items?select=*`, {
        headers: {
          'apikey': CLOUD_CONFIG.key,
          'Authorization': `Bearer ${CLOUD_CONFIG.key}`
        }
      });
      if (!response.ok) throw new Error('Cloud Fetch Failed');
      return await response.json();
    } catch (error) {
      console.error("Lỗi kết nối Database:", error);
      return fallbackData;
    }
  },

  // Đẩy truyện mới lên Cloud
  saveItem: async (item: ContentItem): Promise<boolean> => {
    if (!isCloudEnabled()) {
      // Lưu local nếu không có cloud
      const saved = localStorage.getItem('manganexus_data');
      const items = saved ? JSON.parse(saved) : [];
      const index = items.findIndex((i: any) => i.id === item.id);
      if (index > -1) items[index] = item; else items.unshift(item);
      localStorage.setItem('manganexus_data', JSON.stringify(items));
      return true;
    }

    try {
      const response = await fetch(`${CLOUD_CONFIG.url}/rest/v1/manga_items`, {
        method: 'POST',
        headers: {
          'apikey': CLOUD_CONFIG.key,
          'Authorization': `Bearer ${CLOUD_CONFIG.key}`,
          'Content-Type': 'application/json',
          'Prefer': 'resolution=merge-duplicates'
        },
        body: JSON.stringify(item)
      });
      return response.ok;
    } catch (error) {
      console.error("Lỗi lưu Cloud:", error);
      return false;
    }
  },

  // Xóa truyện khỏi Cloud
  removeItem: async (id: string): Promise<boolean> => {
    if (!isCloudEnabled()) {
      const saved = localStorage.getItem('manganexus_data');
      if (saved) {
        const items = JSON.parse(saved).filter((i: any) => i.id !== id);
        localStorage.setItem('manganexus_data', JSON.stringify(items));
      }
      return true;
    }

    try {
      const response = await fetch(`${CLOUD_CONFIG.url}/rest/v1/manga_items?id=eq.${id}`, {
        method: 'DELETE',
        headers: {
          'apikey': CLOUD_CONFIG.key,
          'Authorization': `Bearer ${CLOUD_CONFIG.key}`
        }
      });
      return response.ok;
    } catch (error) {
      return false;
    }
  }
};
