export const CITY_COORDS: Record<string, [number, number]> = {
  Bengaluru: [12.97, 77.59], Mumbai: [19.08, 72.88], Kolkata: [22.57, 88.36], Chennai: [13.08, 80.27],
  Delhi: [28.61, 77.21], Pune: [18.52, 73.86], Hyderabad: [17.39, 78.49], Frankfurt: [50.11, 8.68],
  Singapore: [1.35, 103.82], London: [51.51, -0.13], Moscow: [55.76, 37.62], Lagos: [6.52, 3.38],
  "New York": [40.71, -74.01], Dubai: [25.2, 55.27],
};

export type LocationStat = { location: string; logins: number; unusual: number; users: string[] };
