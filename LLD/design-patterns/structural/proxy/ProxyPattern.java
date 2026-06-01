import java.util.*;

public class ProxyPattern {

    // ==================== VIRTUAL PROXY ====================

    interface Image {
        void display();
    }

    static class RealImage implements Image {
        private String filename;

        public RealImage(String filename) {
            this.filename = filename;
            loadFromDisk();
        }

        private void loadFromDisk() {
            System.out.println("  [RealImage] Loading image from disk: " + filename);
            try { Thread.sleep(100); } catch (InterruptedException e) {}
        }

        @Override
        public void display() {
            System.out.println("  [RealImage] Displaying: " + filename);
        }
    }

    static class ProxyImage implements Image {
        private String filename;
        private RealImage realImage;

        public ProxyImage(String filename) {
            this.filename = filename;
        }

        @Override
        public void display() {
            if (realImage == null) {
                System.out.println("  [ProxyImage] First access - creating RealImage...");
                realImage = new RealImage(filename);
            }
            realImage.display();
        }
    }

    // ==================== PROTECTION PROXY ====================

    interface Document {
        String read();
        void write(String content);
    }

    static class SensitiveDocument implements Document {
        private String content;
        private String name;

        public SensitiveDocument(String name, String content) {
            this.name = name;
            this.content = content;
        }

        @Override
        public String read() { return content; }

        @Override
        public void write(String content) { this.content = content; }
    }

    static class SecureDocumentProxy implements Document {
        private SensitiveDocument document;
        private String userRole;

        public SecureDocumentProxy(SensitiveDocument document, String userRole) {
            this.document = document;
            this.userRole = userRole;
        }

        @Override
        public String read() {
            if (userRole.equals("ADMIN") || userRole.equals("VIEWER")) {
                System.out.println("  [SecureProxy] Access GRANTED for read (role: " + userRole + ")");
                return document.read();
            }
            System.out.println("  [SecureProxy] Access DENIED for read (role: " + userRole + ")");
            return null;
        }

        @Override
        public void write(String content) {
            if (userRole.equals("ADMIN")) {
                System.out.println("  [SecureProxy] Access GRANTED for write (role: " + userRole + ")");
                document.write(content);
            } else {
                System.out.println("  [SecureProxy] Access DENIED for write (role: " + userRole + ")");
            }
        }
    }

    // ==================== CACHING PROXY ====================

    interface DatabaseService {
        String query(String sql);
    }

    static class RealDatabaseService implements DatabaseService {
        @Override
        public String query(String sql) {
            System.out.println("  [RealDB] Executing expensive query: " + sql);
            try { Thread.sleep(50); } catch (InterruptedException e) {}
            return "Result for: " + sql;
        }
    }

    static class CachingDatabaseProxy implements DatabaseService {
        private RealDatabaseService realService;
        private Map<String, String> cache = new HashMap<>();

        public CachingDatabaseProxy(RealDatabaseService realService) {
            this.realService = realService;
        }

        @Override
        public String query(String sql) {
            if (cache.containsKey(sql)) {
                System.out.println("  [CacheProxy] Cache HIT for: " + sql);
                return cache.get(sql);
            }
            System.out.println("  [CacheProxy] Cache MISS for: " + sql);
            String result = realService.query(sql);
            cache.put(sql, result);
            return result;
        }
    }

    // ==================== LOGGING PROXY ====================

    interface PaymentService {
        boolean processPayment(String userId, double amount);
    }

    static class RealPaymentService implements PaymentService {
        @Override
        public boolean processPayment(String userId, double amount) {
            System.out.println("  [RealPayment] Processing $" + amount + " for user: " + userId);
            return true;
        }
    }

    static class LoggingServiceProxy implements PaymentService {
        private PaymentService realService;

        public LoggingServiceProxy(PaymentService realService) {
            this.realService = realService;
        }

        @Override
        public boolean processPayment(String userId, double amount) {
            long start = System.currentTimeMillis();
            System.out.println("  [LogProxy] >>> Calling processPayment(userId=" + userId + ", amount=" + amount + ")");

            boolean result = realService.processPayment(userId, amount);

            long elapsed = System.currentTimeMillis() - start;
            System.out.println("  [LogProxy] <<< processPayment returned " + result + " in " + elapsed + "ms");
            return result;
        }
    }

    // ==================== MAIN ====================

    public static void main(String[] args) {
        System.out.println("=== VIRTUAL PROXY (Lazy Loading) ===");
        Image img1 = new ProxyImage("photo1.jpg");
        Image img2 = new ProxyImage("photo2.jpg");
        System.out.println("Images created but NOT loaded yet.\n");
        img1.display();
        System.out.println();
        img1.display(); // second call - no reload
        System.out.println();

        System.out.println("=== PROTECTION PROXY (Access Control) ===");
        SensitiveDocument doc = new SensitiveDocument("secrets.txt", "TOP SECRET DATA");
        Document adminProxy = new SecureDocumentProxy(doc, "ADMIN");
        Document guestProxy = new SecureDocumentProxy(doc, "GUEST");

        System.out.println("Admin reading: " + adminProxy.read());
        adminProxy.write("NEW CONTENT");
        System.out.println("Guest reading: " + guestProxy.read());
        guestProxy.write("HACKED");
        System.out.println();

        System.out.println("=== CACHING PROXY ===");
        DatabaseService db = new CachingDatabaseProxy(new RealDatabaseService());
        db.query("SELECT * FROM users");
        db.query("SELECT * FROM users");  // cache hit
        db.query("SELECT * FROM orders");
        System.out.println();

        System.out.println("=== LOGGING PROXY ===");
        PaymentService payment = new LoggingServiceProxy(new RealPaymentService());
        payment.processPayment("user123", 99.99);
        payment.processPayment("user456", 250.00);
    }
}
