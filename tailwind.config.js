// main.py が生成した public/**/*.html から、使っているクラスだけを public/css/site.css に書き出す
module.exports = {
  content: ['./public/**/*.html'],
  theme: {
    extend: {
      colors: { ink: { DEFAULT: '#2b3150', soft: '#555d80' }, cream: '#fffaf3' },
      boxShadow: { soft: '0 1px 2px rgba(43,49,80,.05), 0 12px 32px -12px rgba(43,49,80,.18)' },
    },
  },
};
