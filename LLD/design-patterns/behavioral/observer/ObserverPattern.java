import java.util.*;

/**
 * Observer Design Pattern - Complete Implementation
 * 
 * Defines a one-to-many dependency between objects so that when one object
 * changes state, all its dependents are notified and updated automatically.
 */
public class ObserverPattern {

    // ==================== EXAMPLE 1: Stock Market ====================

    // Observer Interface
    interface StockObserver {
        void update(String stockSymbol, double price);
    }

    // Subject Interface
    interface StockPublisher {
        void subscribe(StockObserver observer);
        void unsubscribe(StockObserver observer);
        void notifyObservers(String stockSymbol, double price);
    }

    // Concrete Subject
    static class StockMarket implements StockPublisher {
        private final List<StockObserver> observers = new ArrayList<>();
        private final Map<String, Double> stockPrices = new HashMap<>();

        @Override
        public void subscribe(StockObserver observer) {
            observers.add(observer);
            System.out.println("  [StockMarket] New subscriber added. Total: " + observers.size());
        }

        @Override
        public void unsubscribe(StockObserver observer) {
            observers.remove(observer);
            System.out.println("  [StockMarket] Subscriber removed. Total: " + observers.size());
        }

        @Override
        public void notifyObservers(String stockSymbol, double price) {
            for (StockObserver observer : observers) {
                observer.update(stockSymbol, price);
            }
        }

        public void setStockPrice(String symbol, double price) {
            double oldPrice = stockPrices.getOrDefault(symbol, 0.0);
            stockPrices.put(symbol, price);
            System.out.printf("%n  >> Stock %s changed: $%.2f -> $%.2f%n", symbol, oldPrice, price);
            notifyObservers(symbol, price);
        }
    }

    // Concrete Observers
    static class MobileApp implements StockObserver {
        private final String userName;

        MobileApp(String userName) { this.userName = userName; }

        @Override
        public void update(String stockSymbol, double price) {
            System.out.printf("     [MobileApp] Push notification to %s: %s is now $%.2f%n",
                    userName, stockSymbol, price);
        }
    }

    static class WebDashboard implements StockObserver {
        @Override
        public void update(String stockSymbol, double price) {
            System.out.printf("     [WebDashboard] Updating chart for %s: $%.2f%n", stockSymbol, price);
        }
    }

    static class EmailAlert implements StockObserver {
        private final String email;
        private final double threshold;

        EmailAlert(String email, double threshold) {
            this.email = email;
            this.threshold = threshold;
        }

        @Override
        public void update(String stockSymbol, double price) {
            if (price > threshold) {
                System.out.printf("     [EmailAlert] Sending alert to %s: %s exceeded $%.2f (now $%.2f)%n",
                        email, stockSymbol, threshold, price);
            }
        }
    }

    static class TradingBot implements StockObserver {
        private final String strategy;

        TradingBot(String strategy) { this.strategy = strategy; }

        @Override
        public void update(String stockSymbol, double price) {
            System.out.printf("     [TradingBot-%s] Analyzing %s at $%.2f... executing strategy%n",
                    strategy, stockSymbol, price);
        }
    }

    // ==================== EXAMPLE 2: Event-Driven Editor ====================

    // Generic Event System
    interface EventListener {
        void update(String eventType, String data);
    }

    static class EventManager {
        private final Map<String, List<EventListener>> listeners = new HashMap<>();

        public EventManager(String... eventTypes) {
            for (String type : eventTypes) {
                listeners.put(type, new ArrayList<>());
            }
        }

        public void subscribe(String eventType, EventListener listener) {
            listeners.get(eventType).add(listener);
        }

        public void unsubscribe(String eventType, EventListener listener) {
            listeners.get(eventType).remove(listener);
        }

        public void notify(String eventType, String data) {
            for (EventListener listener : listeners.getOrDefault(eventType, Collections.emptyList())) {
                listener.update(eventType, data);
            }
        }
    }

    // Concrete Subject using EventManager
    static class Editor {
        public final EventManager events;
        private String currentFile;

        Editor() {
            this.events = new EventManager("open", "save", "close");
        }

        public void openFile(String filePath) {
            this.currentFile = filePath;
            System.out.printf("%n  >> Editor: Opening file '%s'%n", filePath);
            events.notify("open", filePath);
        }

        public void saveFile() {
            System.out.printf("%n  >> Editor: Saving file '%s'%n", currentFile);
            events.notify("save", currentFile);
        }

        public void closeFile() {
            System.out.printf("%n  >> Editor: Closing file '%s'%n", currentFile);
            events.notify("close", currentFile);
            currentFile = null;
        }
    }

    // Concrete Listeners for Editor
    static class LoggingListener implements EventListener {
        @Override
        public void update(String eventType, String data) {
            System.out.printf("     [Logger] Event '%s' on file: %s%n", eventType, data);
        }
    }

    static class EmailNotificationListener implements EventListener {
        private final String adminEmail;

        EmailNotificationListener(String adminEmail) { this.adminEmail = adminEmail; }

        @Override
        public void update(String eventType, String data) {
            System.out.printf("     [Email] Notifying %s: file '%s' was %sed%n",
                    adminEmail, data, eventType);
        }
    }

    static class AutoBackupListener implements EventListener {
        @Override
        public void update(String eventType, String data) {
            System.out.printf("     [AutoBackup] Creating backup of '%s' after %s event%n", data, eventType);
        }
    }

    // ==================== MAIN ====================

    public static void main(String[] args) {
        System.out.println("╔══════════════════════════════════════════════════════╗");
        System.out.println("║         OBSERVER DESIGN PATTERN DEMO                ║");
        System.out.println("╚══════════════════════════════════════════════════════╝");

        // --- Example 1: Stock Market ---
        System.out.println("\n━━━ EXAMPLE 1: Stock Market (Multiple Observers) ━━━");

        StockMarket market = new StockMarket();

        MobileApp mobileApp = new MobileApp("Alice");
        WebDashboard dashboard = new WebDashboard();
        EmailAlert emailAlert = new EmailAlert("bob@mail.com", 150.0);
        TradingBot bot = new TradingBot("Momentum");

        System.out.println("\n--- Subscribing all observers ---");
        market.subscribe(mobileApp);
        market.subscribe(dashboard);
        market.subscribe(emailAlert);
        market.subscribe(bot);

        market.setStockPrice("AAPL", 145.50);
        market.setStockPrice("AAPL", 155.00);

        System.out.println("\n--- Unsubscribing TradingBot ---");
        market.unsubscribe(bot);

        market.setStockPrice("GOOGL", 2800.00);

        // --- Example 2: Event-Driven Editor ---
        System.out.println("\n\n━━━ EXAMPLE 2: Event-Driven Editor System ━━━");

        Editor editor = new Editor();

        LoggingListener logger = new LoggingListener();
        EmailNotificationListener emailListener = new EmailNotificationListener("admin@company.com");
        AutoBackupListener backup = new AutoBackupListener();

        editor.events.subscribe("open", logger);
        editor.events.subscribe("save", logger);
        editor.events.subscribe("save", emailListener);
        editor.events.subscribe("save", backup);
        editor.events.subscribe("close", logger);

        editor.openFile("design-patterns.txt");
        editor.saveFile();

        System.out.println("\n--- Removing email listener from save events ---");
        editor.events.unsubscribe("save", emailListener);

        editor.saveFile();
        editor.closeFile();

        System.out.println("\n━━━ DEMO COMPLETE ━━━");
    }
}
