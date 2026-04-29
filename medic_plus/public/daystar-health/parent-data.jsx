// Daystar Merchandising — mock data
const PRODUCTS = [
  { id: 'DSM-1042', name: 'Heritage Tomato Sauce', category: 'Pantry', subcat: 'Sauces', size: '12 oz', price: 4.49, cost: 1.92, stock: 1842, reserved: 124, sold30d: 4210, status: 'In stock', supplier: 'Verde Foods Co.', rating: 4.7, margin: 57.2, trend: [62, 68, 64, 71, 78, 82, 89, 84, 91, 95, 88, 96] },
  { id: 'DSM-2087', name: 'Sea Salt Sourdough', category: 'Bakery', subcat: 'Bread', size: '680 g', price: 6.99, cost: 2.85, stock: 184, reserved: 18, sold30d: 2890, status: 'Low stock', supplier: 'Stoneground Bakery', rating: 4.9, margin: 59.2, trend: [40, 45, 52, 58, 61, 66, 70, 74, 71, 75, 78, 82] },
  { id: 'DSM-3019', name: 'Cold Brew Concentrate', category: 'Beverages', subcat: 'Coffee', size: '32 fl oz', price: 12.99, cost: 4.20, stock: 0, reserved: 0, sold30d: 1240, status: 'Out of stock', supplier: 'North Roasters', rating: 4.6, margin: 67.7, trend: [88, 84, 80, 72, 65, 54, 42, 30, 22, 14, 8, 0] },
  { id: 'DSM-4451', name: 'Organic Whole Milk', category: 'Dairy', subcat: 'Milk', size: '64 fl oz', price: 5.49, cost: 2.10, stock: 2410, reserved: 220, sold30d: 8920, status: 'In stock', supplier: 'Pasture Bend Farms', rating: 4.8, margin: 61.7, trend: [70, 72, 75, 73, 78, 80, 84, 87, 89, 88, 91, 93] },
  { id: 'DSM-5523', name: 'Spiced Apple Cider', category: 'Beverages', subcat: 'Juice', size: '64 fl oz', price: 7.99, cost: 2.95, stock: 612, reserved: 42, sold30d: 1180, status: 'In stock', supplier: 'Orchard Lane', rating: 4.5, margin: 63.1, trend: [45, 48, 52, 55, 58, 62, 65, 68, 71, 70, 72, 74] },
  { id: 'DSM-6112', name: 'Aged Cheddar Wedge', category: 'Dairy', subcat: 'Cheese', size: '8 oz', price: 9.49, cost: 3.80, stock: 96, reserved: 14, sold30d: 1890, status: 'Low stock', supplier: 'Hollow Creek Creamery', rating: 4.9, margin: 60.0, trend: [60, 62, 65, 64, 68, 70, 72, 71, 74, 76, 78, 80] },
  { id: 'DSM-7034', name: 'Honey-Roasted Granola', category: 'Pantry', subcat: 'Cereal', size: '14 oz', price: 8.99, cost: 3.10, stock: 1340, reserved: 88, sold30d: 2180, status: 'In stock', supplier: 'Meadow Pantry', rating: 4.7, margin: 65.5, trend: [50, 53, 56, 60, 63, 65, 68, 70, 73, 75, 77, 79] },
  { id: 'DSM-8201', name: 'Wild Caught Smoked Salmon', category: 'Seafood', subcat: 'Smoked', size: '6 oz', price: 16.99, cost: 7.50, stock: 218, reserved: 36, sold30d: 980, status: 'In stock', supplier: 'Coastline Seafood', rating: 4.8, margin: 55.9, trend: [42, 45, 48, 50, 52, 55, 58, 60, 62, 64, 65, 67] },
  { id: 'DSM-9117', name: 'Single-Origin Dark Chocolate', category: 'Snacks', subcat: 'Confectionery', size: '3.5 oz', price: 5.99, cost: 1.85, stock: 1820, reserved: 145, sold30d: 3120, status: 'In stock', supplier: 'Cocoa & Co.', rating: 4.9, margin: 69.1, trend: [65, 68, 70, 73, 76, 78, 81, 83, 86, 88, 90, 92] },
  { id: 'DSM-1188', name: 'Sparkling Mineral Water', category: 'Beverages', subcat: 'Water', size: '750 ml', price: 3.49, cost: 0.95, stock: 4280, reserved: 312, sold30d: 6420, status: 'In stock', supplier: 'Glacier Springs', rating: 4.6, margin: 72.8, trend: [80, 82, 85, 87, 90, 88, 92, 94, 91, 93, 95, 97] },
  { id: 'DSM-1290', name: 'Cracked Pepper Crackers', category: 'Snacks', subcat: 'Crackers', size: '8 oz', price: 4.99, cost: 1.40, stock: 28, reserved: 4, sold30d: 1240, status: 'Low stock', supplier: 'Mill House', rating: 4.5, margin: 71.9, trend: [55, 56, 58, 60, 62, 64, 65, 67, 68, 69, 70, 72] },
  { id: 'DSM-1342', name: 'Free-Range Brown Eggs', category: 'Dairy', subcat: 'Eggs', size: '12 ct', price: 6.49, cost: 2.40, stock: 1120, reserved: 96, sold30d: 5240, status: 'In stock', supplier: 'Pasture Bend Farms', rating: 4.8, margin: 63.0, trend: [72, 74, 76, 78, 80, 82, 84, 86, 88, 89, 90, 92] },
];

const ORDERS = [
  { id: '#PO-67142', date: 'Apr 28', vendor: 'Verde Foods Co.', items: 12, amount: 4280.00, status: 'Delivered', method: 'Net 30' },
  { id: '#PO-67098', date: 'Apr 27', vendor: 'Stoneground Bakery', items: 4, amount: 892.50, status: 'In transit', method: 'Net 15' },
  { id: '#PO-67051', date: 'Apr 26', vendor: 'North Roasters', items: 8, amount: 1840.00, status: 'Pending', method: 'Net 30' },
  { id: '#PO-67012', date: 'Apr 25', vendor: 'Pasture Bend Farms', items: 18, amount: 6210.75, status: 'Delivered', method: 'Net 30' },
  { id: '#PO-66988', date: 'Apr 24', vendor: 'Orchard Lane', items: 6, amount: 720.40, status: 'Delivered', method: 'Net 15' },
  { id: '#PO-66954', date: 'Apr 23', vendor: 'Hollow Creek Creamery', items: 9, amount: 1480.00, status: 'Cancelled', method: 'Net 30' },
  { id: '#PO-66921', date: 'Apr 22', vendor: 'Meadow Pantry', items: 5, amount: 980.20, status: 'Delivered', method: 'Net 30' },
  { id: '#PO-66887', date: 'Apr 21', vendor: 'Coastline Seafood', items: 3, amount: 1620.00, status: 'In transit', method: 'Wire' },
];

const STORES = [
  { id: 'DT-01', name: 'Daystar Downtown', city: 'Brooklyn, NY', staff: 14, sales: 184200 },
  { id: 'WS-02', name: 'Daystar Westside', city: 'Portland, OR', staff: 11, sales: 142800 },
  { id: 'NB-03', name: 'Daystar North Bay', city: 'Oakland, CA', staff: 9, sales: 98400 },
  { id: 'CV-04', name: 'Daystar Central Valley', city: 'Austin, TX', staff: 12, sales: 156200 },
];

window.DSM_DATA = { PRODUCTS, ORDERS, STORES };
