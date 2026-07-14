export type MonthRecord = {
  month: string;
  netSales: number;
};

export type CountryRecord = {
  country: string;
  netSales: number;
};

export const monthlySales: MonthRecord[] = [
  { month: "2009-12", netSales: 799443 },
  { month: "2010-01", netSales: 642121 },
  { month: "2010-02", netSales: 535804 },
  { month: "2010-03", netSales: 758133 },
  { month: "2010-04", netSales: 642054 },
  { month: "2010-05", netSales: 611336 },
  { month: "2010-06", netSales: 674925 },
  { month: "2010-07", netSales: 615246 },
  { month: "2010-08", netSales: 655312 },
  { month: "2010-09", netSales: 839725 },
  { month: "2010-10", netSales: 1036680 },
  { month: "2010-11", netSales: 1422654 },
  { month: "2010-12", netSales: 568012 },
  { month: "2011-01", netSales: 493642 },
  { month: "2011-02", netSales: 675121 },
  { month: "2011-03", netSales: 497613 },
  { month: "2011-04", netSales: 716326 },
  { month: "2011-05", netSales: 682411 },
  { month: "2011-06", netSales: 671244 },
  { month: "2011-07", netSales: 703186 },
  { month: "2011-08", netSales: 1018888 },
  { month: "2011-09", netSales: 1065774 },
  { month: "2011-10", netSales: 1453893 },
  { month: "2011-11", netSales: 433662 },
];

export const countrySales: CountryRecord[] = [
  { country: "United Kingdom", netSales: 16830840 },
  { country: "EIRE", netSales: 581235 },
  { country: "Netherlands", netSales: 554771 },
  { country: "Germany", netSales: 417928 },
  { country: "France", netSales: 356184 },
  { country: "Australia", netSales: 169968 },
  { country: "Switzerland", netSales: 124871 },
];

export const productSales = [
  { label: "22423", value: 338702 },
  { label: "DOT", value: 334129 },
  { label: "85123A", value: 268221 },
  { label: "85099B", value: 198364 },
  { label: "47566", value: 163890 },
  { label: "84879", value: 146202 },
];

export const customerSales = [
  { label: "Unassigned", value: 2751689 },
  { label: "18102", value: 614289 },
  { label: "14646", value: 539142 },
  { label: "14156", value: 301168 },
];

export const baseline = {
  netSales: 19_450_000,
  orderCount: 40_000,
  unitsSold: 1_100_000,
  activeCustomers: 6_000,
  averageOrderValue: 523.31,
  cancellationRate: 0.1546,
  cancelledSales: 1_530_000,
};
