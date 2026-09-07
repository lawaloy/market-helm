/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'strong-buy': '#10B981',
        buy: '#34D399',
        hold: '#64748B',
        sell: '#F59E0B',
        'strong-sell': '#EF4444',
        'risk-low': '#10B981',
        'risk-medium': '#F59E0B',
        'risk-high': '#EF4444',
        bullish: '#10B981',
        neutral: '#64748B',
        bearish: '#EF4444',
      },
    },
  },
  plugins: [],
};
