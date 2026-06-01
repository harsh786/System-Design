/**
 * Factory Method Design Pattern - Notification System Example
 *
 * The Factory Method pattern defines an interface for creating objects,
 * but lets subclasses decide which class to instantiate.
 */

// ─── Product Interface ───────────────────────────────────────────────────────

interface Notification {
    void notifyUser(String message);
    String getChannel();
}

// ─── Concrete Products ───────────────────────────────────────────────────────

class EmailNotification implements Notification {
    private final String emailAddress;

    public EmailNotification(String emailAddress) {
        this.emailAddress = emailAddress;
    }

    @Override
    public void notifyUser(String message) {
        System.out.println("[EMAIL] To: " + emailAddress);
        System.out.println("        Message: " + message);
    }

    @Override
    public String getChannel() {
        return "Email";
    }
}

class SMSNotification implements Notification {
    private final String phoneNumber;

    public SMSNotification(String phoneNumber) {
        this.phoneNumber = phoneNumber;
    }

    @Override
    public void notifyUser(String message) {
        System.out.println("[SMS] To: " + phoneNumber);
        System.out.println("      Message: " + message);
    }

    @Override
    public String getChannel() {
        return "SMS";
    }
}

class PushNotification implements Notification {
    private final String deviceToken;

    public PushNotification(String deviceToken) {
        this.deviceToken = deviceToken;
    }

    @Override
    public void notifyUser(String message) {
        System.out.println("[PUSH] Device: " + deviceToken);
        System.out.println("       Message: " + message);
    }

    @Override
    public String getChannel() {
        return "Push";
    }
}

// ─── Creator (Abstract Factory) ─────────────────────────────────────────────

abstract class NotificationFactory {
    // Factory Method - subclasses override this
    public abstract Notification createNotification(String recipient);

    // Template method that uses the factory method
    public void sendNotification(String recipient, String message) {
        Notification notification = createNotification(recipient);
        System.out.println("Sending via " + notification.getChannel() + " channel...");
        notification.notifyUser(message);
        System.out.println();
    }
}

// ─── Concrete Creators ───────────────────────────────────────────────────────

class EmailNotificationFactory extends NotificationFactory {
    @Override
    public Notification createNotification(String recipient) {
        return new EmailNotification(recipient);
    }
}

class SMSNotificationFactory extends NotificationFactory {
    @Override
    public Notification createNotification(String recipient) {
        return new SMSNotification(recipient);
    }
}

class PushNotificationFactory extends NotificationFactory {
    @Override
    public Notification createNotification(String recipient) {
        return new PushNotification(recipient);
    }
}

// ─── Client Code ─────────────────────────────────────────────────────────────

public class FactoryMethodPattern {
    public static void main(String[] args) {
        System.out.println("=== Factory Method Pattern: Notification System ===\n");

        NotificationFactory[] factories = {
            new EmailNotificationFactory(),
            new SMSNotificationFactory(),
            new PushNotificationFactory()
        };

        String[][] recipients = {
            {"user@example.com"},
            {"+1-555-0123"},
            {"device-token-abc123"}
        };

        String message = "Your order #1234 has been shipped!";

        for (int i = 0; i < factories.length; i++) {
            factories[i].sendNotification(recipients[i][0], message);
        }

        // Demonstrating that client code works with any factory
        System.out.println("--- Dynamic factory selection ---\n");
        String preferredChannel = "sms";
        NotificationFactory factory = getFactory(preferredChannel);
        factory.sendNotification("+1-555-9999", "Welcome aboard!");
    }

    // Simulates runtime factory selection
    private static NotificationFactory getFactory(String channel) {
        switch (channel.toLowerCase()) {
            case "email": return new EmailNotificationFactory();
            case "sms":   return new SMSNotificationFactory();
            case "push":  return new PushNotificationFactory();
            default: throw new IllegalArgumentException("Unknown channel: " + channel);
        }
    }
}
