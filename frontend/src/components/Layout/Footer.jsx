import './Layout.css';

const CURRENT_YEAR = new Date().getFullYear();

export default function Footer() {
  return (
    <footer className="footer" role="contentinfo">
      <div className="container footer__inner">
        <div className="footer__brand">
          <div className="footer__brand-name">🥖 BakeCart B2B</div>
          <p className="footer__brand-tagline">Commercial Bakery Wholesale Ordering & Fulfillment Platform</p>
        </div>
      </div>
      <div className="container">
        <p className="footer__copy">
          © {CURRENT_YEAR} BakeCart 2.0. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
