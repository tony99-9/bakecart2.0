import Navbar from './Navbar';
import Footer from './Footer';

/**
 * Root layout: fixed navbar + scrollable content + footer.
 * All pages are rendered as {children}.
 */
export default function Layout({ children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Navbar />
      <main id="main-content" style={{ flex: 1 }}>
        {children}
      </main>
      <Footer />
    </div>
  );
}
