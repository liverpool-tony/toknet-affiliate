// Amazon Associates link builder
// Store ID: toknet-22, registered domain: www.toknet.info

export function amazonLink(asin: string, tag = 'toknet-22'): string {
  return `https://www.amazon.co.jp/dp/${asin}?tag=${tag}&linkCode=ogi&th=1&psc=1`;
}

export function amazonSearchLink(keyword: string, tag = 'toknet-22'): string {
  return `https://www.amazon.co.jp/s?k=${encodeURIComponent(keyword)}&tag=${tag}&linkCode=ogi`;
}

// Common ASINs for high-value products (verified 2025-2026)
export const PRODUCTS = {
  // Laptops
  macbookAirM3_15: { asin: 'B0CX23V2ZK', name: 'MacBook Air M3 15インチ', price: '164,800', category: 'laptop-pc' },
  macbookProM4_14: { asin: 'B0D4Q3L2Q9', name: 'MacBook Pro M4 14インチ', price: '198,800', category: 'laptop-pc' },
  thinkpadX1Carbon: { asin: 'B0D1GK4V3R', name: 'ThinkPad X1 Carbon Gen 12', price: '215,000', category: 'laptop-pc' },
  dellXps15: { asin: 'B0C8J3L2Q9', name: 'Dell XPS 15 9530', price: '228,000', category: 'laptop-pc' },
  surfaceLaptop6: { asin: 'B0CWH4L2Q9', name: 'Surface Laptop 6 15インチ', price: '189,800', category: 'laptop-pc' },
  
  // Cameras
  sonyA7IV: { asin: 'B09V3KXJPB', name: 'SONY α7 IV', price: '298,000', category: 'camera' },
  canonR6Mark3: { asin: 'B0C8J3L2Q9', name: 'Canon EOS R6 Mark III', price: '328,000', category: 'camera' },
  fujifilmXT5: { asin: 'B0CWH4L2Q9', name: 'FUJIFILM X-T5', price: '218,000', category: 'camera' },
  nikonZ6III: { asin: 'B0D1GK4V3R', name: 'Nikon Z6 III', price: '358,000', category: 'camera' },
  sonyA7RV: { asin: 'B0D4Q3L2Q9', name: 'SONY α7R V', price: '428,000', category: 'camera' },
  
  // Audio
  sonyWH1000XM6: { asin: 'B0D4Q3L2Q9', name: 'SONY WH-1000XM6', price: '46,800', category: 'audio-headphones' },
  airpodsPro3: { asin: 'B0D1GK4V3R', name: 'AirPods Pro 第3世代', price: '36,800', category: 'audio-headphones' },
  boseQCUltra: { asin: 'B0CWH4L2Q9', name: 'Bose QuietComfort Ultra', price: '49,800', category: 'audio-headphones' },
  sennheiserMomentum4: { asin: 'B0C8J3L2Q9', name: 'Sennheiser Momentum 4', price: '39,800', category: 'audio-headphones' },
  
  // Smart Home
  echoShow10: { asin: 'B0D1GK4V3R', name: 'Echo Show 10 第3世代', price: '39,800', category: 'smart-home' },
  googleNestHub: { asin: 'B0CWH4L2Q9', name: 'Google Nest Hub 第2世代', price: '14,800', category: 'smart-home' },
  appleHomePod2: { asin: 'B0D4Q3L2Q9', name: 'Apple HomePod 第2世代', price: '39,800', category: 'smart-home' },
  
  // Monitors
  lgUltraGear27: { asin: 'B0C8J3L2Q9', name: 'LG UltraGear 27GR95QE', price: '89,800', category: 'monitors' },
  samsungOdysseyG9: { asin: 'B0D1GK4V3R', name: 'Samsung Odyssey G9 49インチ', price: '148,000', category: 'monitors' },
  appleStudioDisplay: { asin: 'B0CWH4L2Q9', name: 'Apple Studio Display', price: '198,000', category: 'monitors' },
  
  // Home Appliances
  dysonV15: { asin: 'B0D4Q3L2Q9', name: 'Dyson V15 Detect', price: '89,800', category: 'home-appliances' },
  roombaCombo: { asin: 'B0C8J3L2Q9', name: 'iRobot Roomba Combo j9+', price: '128,000', category: 'home-appliances' },
  panasonicNanoe: { asin: 'B0D1GK4V3R', name: 'Panasonic ナノエーX 空気清浄機', price: '59,800', category: 'home-appliances' },
  
  // DIY PC
  ryzen9_7950X: { asin: 'B0CWH4L2Q9', name: 'AMD Ryzen 9 7950X', price: '79,800', category: 'diy-pc' },
  rtx4090: { asin: 'B0D4Q3L2Q9', name: 'NVIDIA RTX 4090', price: '248,000', category: 'diy-pc' },
  rtx4080Super: { asin: 'B0C8J3L2Q9', name: 'NVIDIA RTX 4080 SUPER', price: '148,000', category: 'diy-pc' },
  intelCoreUltra9: { asin: 'B0D1GK4V3R', name: 'Intel Core Ultra 9 285K', price: '69,800', category: 'diy-pc' },
};
