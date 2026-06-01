/**
 * Adapter Design Pattern - Structural Pattern
 * 
 * Converts the interface of a class into another interface that clients expect.
 * Lets classes work together that couldn't otherwise because of incompatible interfaces.
 */

// ==================== EXAMPLE 1: Media Player (Object Adapter) ====================

// Target Interface - what the client expects
interface MediaPlayer {
    void play(String audioType, String fileName);
}

// Adaptee Interface - the incompatible interface
interface AdvancedMediaPlayer {
    void playVlc(String fileName);
    void playMp4(String fileName);
}

// Concrete Adaptees
class VlcPlayer implements AdvancedMediaPlayer {
    @Override
    public void playVlc(String fileName) {
        System.out.println("  [VLC Engine] Playing vlc file: " + fileName);
    }

    @Override
    public void playMp4(String fileName) {
        // do nothing
    }
}

class Mp4Player implements AdvancedMediaPlayer {
    @Override
    public void playVlc(String fileName) {
        // do nothing
    }

    @Override
    public void playMp4(String fileName) {
        System.out.println("  [MP4 Engine] Playing mp4 file: " + fileName);
    }
}

// Object Adapter - uses composition to wrap the adaptee
class MediaAdapter implements MediaPlayer {
    private AdvancedMediaPlayer advancedPlayer;

    public MediaAdapter(String audioType) {
        if (audioType.equalsIgnoreCase("vlc")) {
            advancedPlayer = new VlcPlayer();
        } else if (audioType.equalsIgnoreCase("mp4")) {
            advancedPlayer = new Mp4Player();
        }
    }

    @Override
    public void play(String audioType, String fileName) {
        if (audioType.equalsIgnoreCase("vlc")) {
            advancedPlayer.playVlc(fileName);
        } else if (audioType.equalsIgnoreCase("mp4")) {
            advancedPlayer.playMp4(fileName);
        }
    }
}

// Client - uses the Target interface
class AudioPlayer implements MediaPlayer {
    @Override
    public void play(String audioType, String fileName) {
        if (audioType.equalsIgnoreCase("mp3")) {
            System.out.println("  [Built-in] Playing mp3 file: " + fileName);
        } else if (audioType.equalsIgnoreCase("vlc") || audioType.equalsIgnoreCase("mp4")) {
            MediaAdapter adapter = new MediaAdapter(audioType);
            adapter.play(audioType, fileName);
        } else {
            System.out.println("  [Error] Format not supported: " + audioType);
        }
    }
}

// ==================== EXAMPLE 2: Class Adapter (using inheritance) ====================

// Adaptee - legacy class with incompatible interface
class LegacyRectangle {
    public void drawRect(int x1, int y1, int x2, int y2) {
        System.out.println("  [Legacy] Drawing rectangle from (" + x1 + "," + y1 + ") to (" + x2 + "," + y2 + ")");
    }
}

// Target Interface
interface Shape {
    void draw(int x, int y, int width, int height);
}

// Class Adapter - uses inheritance (extends adaptee, implements target)
class RectangleAdapter extends LegacyRectangle implements Shape {
    @Override
    public void draw(int x, int y, int width, int height) {
        // Translate the interface: (x, y, width, height) -> (x1, y1, x2, y2)
        drawRect(x, y, x + width, y + height);
    }
}

// ==================== EXAMPLE 3: Payment Gateway (Real-World) ====================

// Target Interface - unified payment processor
interface PaymentProcessor {
    boolean pay(String merchantId, double amount, String currency);
    boolean refund(String transactionId, double amount);
    String getProviderName();
}

// Adaptee 1 - PayPal SDK (incompatible interface)
class PayPalSDK {
    public boolean makePayment(String email, double amountInCents) {
        System.out.println("  [PayPal] Processing $" + (amountInCents / 100.0) + " for " + email);
        return true;
    }

    public boolean issueRefund(String paypalTxnId) {
        System.out.println("  [PayPal] Refunding transaction: " + paypalTxnId);
        return true;
    }
}

// Adaptee 2 - Stripe SDK (different incompatible interface)
class StripeAPI {
    public String createCharge(int amountInCents, String curr, String merchantToken) {
        System.out.println("  [Stripe] Charging " + amountInCents + " " + curr + " to merchant " + merchantToken);
        return "ch_" + System.currentTimeMillis();
    }

    public boolean reverseCharge(String chargeId, int amountInCents) {
        System.out.println("  [Stripe] Reversing charge " + chargeId + " for " + amountInCents + " cents");
        return true;
    }
}

// Object Adapter for PayPal
class PayPalAdapter implements PaymentProcessor {
    private PayPalSDK paypal;

    public PayPalAdapter(PayPalSDK paypal) {
        this.paypal = paypal;
    }

    @Override
    public boolean pay(String merchantId, double amount, String currency) {
        // Adapt: convert dollars to cents, merchantId to email format
        double amountInCents = amount * 100;
        return paypal.makePayment(merchantId + "@merchant.com", amountInCents);
    }

    @Override
    public boolean refund(String transactionId, double amount) {
        return paypal.issueRefund(transactionId);
    }

    @Override
    public String getProviderName() {
        return "PayPal";
    }
}

// Object Adapter for Stripe
class StripeAdapter implements PaymentProcessor {
    private StripeAPI stripe;

    public StripeAdapter(StripeAPI stripe) {
        this.stripe = stripe;
    }

    @Override
    public boolean pay(String merchantId, double amount, String currency) {
        // Adapt: convert dollars to cents
        int amountInCents = (int) (amount * 100);
        String chargeId = stripe.createCharge(amountInCents, currency, merchantId);
        return chargeId != null;
    }

    @Override
    public boolean refund(String transactionId, double amount) {
        int amountInCents = (int) (amount * 100);
        return stripe.reverseCharge(transactionId, amountInCents);
    }

    @Override
    public String getProviderName() {
        return "Stripe";
    }
}

// Payment service that works with any adapted gateway
class PaymentService {
    private PaymentProcessor processor;

    public PaymentService(PaymentProcessor processor) {
        this.processor = processor;
    }

    public void processOrder(String merchantId, double amount) {
        System.out.println("  Using provider: " + processor.getProviderName());
        boolean success = processor.pay(merchantId, amount, "USD");
        System.out.println("  Payment " + (success ? "successful" : "failed"));
    }
}

// ==================== MAIN ====================

public class AdapterPattern {
    public static void main(String[] args) {
        System.out.println("=== ADAPTER DESIGN PATTERN ===\n");

        // --- Example 1: Media Player (Object Adapter) ---
        System.out.println("--- Example 1: Media Player (Object Adapter) ---");
        MediaPlayer player = new AudioPlayer();
        player.play("mp3", "song.mp3");
        player.play("mp4", "movie.mp4");
        player.play("vlc", "video.vlc");
        player.play("avi", "clip.avi");

        // --- Example 2: Class Adapter ---
        System.out.println("\n--- Example 2: Shape Drawing (Class Adapter) ---");
        Shape rectangle = new RectangleAdapter();
        rectangle.draw(10, 20, 100, 50);

        // --- Example 3: Payment Gateway ---
        System.out.println("\n--- Example 3: Payment Gateway (Real-World) ---");

        // Using PayPal
        PaymentProcessor paypalProcessor = new PayPalAdapter(new PayPalSDK());
        PaymentService service1 = new PaymentService(paypalProcessor);
        service1.processOrder("shop123", 49.99);

        System.out.println();

        // Using Stripe - same client code, different adapter
        PaymentProcessor stripeProcessor = new StripeAdapter(new StripeAPI());
        PaymentService service2 = new PaymentService(stripeProcessor);
        service2.processOrder("shop123", 49.99);

        System.out.println();

        // Refunds
        System.out.println("  --- Refunds ---");
        paypalProcessor.refund("TXN_001", 49.99);
        stripeProcessor.refund("ch_12345", 49.99);

        System.out.println("\n=== KEY INSIGHT ===");
        System.out.println("The client (PaymentService) works with ANY payment provider");
        System.out.println("without knowing the specifics of PayPal or Stripe APIs.");
        System.out.println("The adapter translates between incompatible interfaces.");
    }
}
