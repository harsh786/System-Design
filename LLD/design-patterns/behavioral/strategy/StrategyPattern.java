import java.util.Arrays;
import java.util.Random;

// ============================================================
// EXAMPLE 1: Payment Processing
// ============================================================

// Strategy Interface
interface PaymentStrategy {
    void pay(double amount);
}

// Concrete Strategy: Credit Card
class CreditCardPayment implements PaymentStrategy {
    private String cardNumber;
    private String name;

    public CreditCardPayment(String cardNumber, String name) {
        this.cardNumber = cardNumber;
        this.name = name;
    }

    @Override
    public void pay(double amount) {
        String masked = "****-****-****-" + cardNumber.substring(cardNumber.length() - 4);
        System.out.println("[CreditCard] Paid $" + amount + " using card " + masked + " (holder: " + name + ")");
    }
}

// Concrete Strategy: PayPal
class PayPalPayment implements PaymentStrategy {
    private String email;

    public PayPalPayment(String email) {
        this.email = email;
    }

    @Override
    public void pay(double amount) {
        System.out.println("[PayPal] Paid $" + amount + " from account " + email);
    }
}

// Concrete Strategy: Cryptocurrency
class CryptocurrencyPayment implements PaymentStrategy {
    private String walletAddress;
    private String coinType;

    public CryptocurrencyPayment(String walletAddress, String coinType) {
        this.walletAddress = walletAddress;
        this.coinType = coinType;
    }

    @Override
    public void pay(double amount) {
        System.out.println("[Crypto] Paid $" + amount + " in " + coinType + " to wallet " + walletAddress.substring(0, 8) + "...");
    }
}

// Concrete Strategy: UPI
class UPIPayment implements PaymentStrategy {
    private String upiId;

    public UPIPayment(String upiId) {
        this.upiId = upiId;
    }

    @Override
    public void pay(double amount) {
        System.out.println("[UPI] Paid $" + amount + " via UPI ID: " + upiId);
    }
}

// Context
class ShoppingCart {
    private PaymentStrategy paymentStrategy;
    private double total;

    public void setPaymentStrategy(PaymentStrategy strategy) {
        this.paymentStrategy = strategy;
    }

    public void addItem(String item, double price) {
        total += price;
        System.out.println("  Added: " + item + " ($" + price + ")");
    }

    public void checkout() {
        if (paymentStrategy == null) {
            throw new IllegalStateException("No payment strategy set!");
        }
        paymentStrategy.pay(total);
        total = 0;
    }
}

// ============================================================
// EXAMPLE 2: Sorting Strategies
// ============================================================

// Strategy Interface
interface SortStrategy {
    int[] sort(int[] data);
    String getName();
}

// Concrete Strategy: Bubble Sort
class BubbleSort implements SortStrategy {
    @Override
    public int[] sort(int[] data) {
        int[] arr = data.clone();
        int n = arr.length;
        for (int i = 0; i < n - 1; i++) {
            for (int j = 0; j < n - i - 1; j++) {
                if (arr[j] > arr[j + 1]) {
                    int temp = arr[j];
                    arr[j] = arr[j + 1];
                    arr[j + 1] = temp;
                }
            }
        }
        return arr;
    }

    @Override
    public String getName() { return "BubbleSort"; }
}

// Concrete Strategy: Quick Sort
class QuickSort implements SortStrategy {
    @Override
    public int[] sort(int[] data) {
        int[] arr = data.clone();
        quickSort(arr, 0, arr.length - 1);
        return arr;
    }

    private void quickSort(int[] arr, int low, int high) {
        if (low < high) {
            int pi = partition(arr, low, high);
            quickSort(arr, low, pi - 1);
            quickSort(arr, pi + 1, high);
        }
    }

    private int partition(int[] arr, int low, int high) {
        int pivot = arr[high];
        int i = low - 1;
        for (int j = low; j < high; j++) {
            if (arr[j] < pivot) {
                i++;
                int temp = arr[i];
                arr[i] = arr[j];
                arr[j] = temp;
            }
        }
        int temp = arr[i + 1];
        arr[i + 1] = arr[high];
        arr[high] = temp;
        return i + 1;
    }

    @Override
    public String getName() { return "QuickSort"; }
}

// Concrete Strategy: Merge Sort
class MergeSort implements SortStrategy {
    @Override
    public int[] sort(int[] data) {
        int[] arr = data.clone();
        mergeSort(arr, 0, arr.length - 1);
        return arr;
    }

    private void mergeSort(int[] arr, int left, int right) {
        if (left < right) {
            int mid = (left + right) / 2;
            mergeSort(arr, left, mid);
            mergeSort(arr, mid + 1, right);
            merge(arr, left, mid, right);
        }
    }

    private void merge(int[] arr, int left, int mid, int right) {
        int[] temp = new int[right - left + 1];
        int i = left, j = mid + 1, k = 0;
        while (i <= mid && j <= right) {
            temp[k++] = arr[i] <= arr[j] ? arr[i++] : arr[j++];
        }
        while (i <= mid) temp[k++] = arr[i++];
        while (j <= right) temp[k++] = arr[j++];
        System.arraycopy(temp, 0, arr, left, temp.length);
    }

    @Override
    public String getName() { return "MergeSort"; }
}

// Context with automatic strategy selection
class SortContext {
    private SortStrategy strategy;

    public void setStrategy(SortStrategy strategy) {
        this.strategy = strategy;
    }

    // Automatically select strategy based on data size
    public void autoSelectStrategy(int dataSize) {
        if (dataSize < 10) {
            this.strategy = new BubbleSort();
        } else if (dataSize < 1000) {
            this.strategy = new QuickSort();
        } else {
            this.strategy = new MergeSort();
        }
        System.out.println("  Auto-selected: " + strategy.getName() + " for " + dataSize + " elements");
    }

    public int[] executeSort(int[] data) {
        if (strategy == null) {
            autoSelectStrategy(data.length);
        }
        long start = System.nanoTime();
        int[] result = strategy.sort(data);
        long elapsed = System.nanoTime() - start;
        System.out.println("  " + strategy.getName() + " completed in " + elapsed / 1000 + " microseconds");
        return result;
    }
}

// ============================================================
// Main Demo
// ============================================================

public class StrategyPattern {
    public static void main(String[] args) {
        System.out.println("=== STRATEGY PATTERN DEMO ===\n");

        // --- Payment Example ---
        System.out.println("--- Example 1: Payment Processing ---\n");

        ShoppingCart cart = new ShoppingCart();
        cart.addItem("Laptop", 999.99);
        cart.addItem("Mouse", 29.99);

        System.out.println("\nCheckout with Credit Card:");
        cart.setPaymentStrategy(new CreditCardPayment("1234567890121234", "John Doe"));
        cart.checkout();

        cart.addItem("Keyboard", 79.99);
        System.out.println("\nSwitch to PayPal at runtime:");
        cart.setPaymentStrategy(new PayPalPayment("john@example.com"));
        cart.checkout();

        cart.addItem("Monitor", 499.99);
        System.out.println("\nSwitch to Crypto:");
        cart.setPaymentStrategy(new CryptocurrencyPayment("0xABCDEF1234567890", "ETH"));
        cart.checkout();

        cart.addItem("Webcam", 59.99);
        System.out.println("\nSwitch to UPI:");
        cart.setPaymentStrategy(new UPIPayment("john@oksbi"));
        cart.checkout();

        // --- Sorting Example ---
        System.out.println("\n--- Example 2: Sorting Strategies ---\n");

        SortContext sorter = new SortContext();
        Random rand = new Random(42);

        // Small array - auto selects BubbleSort
        int[] small = rand.ints(5, 1, 100).toArray();
        System.out.println("Small array: " + Arrays.toString(small));
        sorter.autoSelectStrategy(small.length);
        int[] sorted = sorter.executeSort(small);
        System.out.println("  Result: " + Arrays.toString(sorted) + "\n");

        // Medium array - auto selects QuickSort
        int[] medium = rand.ints(50, 1, 1000).toArray();
        System.out.println("Medium array (" + medium.length + " elements):");
        sorter.autoSelectStrategy(medium.length);
        sorted = sorter.executeSort(medium);
        System.out.println("  First 10: " + Arrays.toString(Arrays.copyOf(sorted, 10)) + "...\n");

        // Large array - auto selects MergeSort
        int[] large = rand.ints(5000, 1, 100000).toArray();
        System.out.println("Large array (" + large.length + " elements):");
        sorter.autoSelectStrategy(large.length);
        sorted = sorter.executeSort(large);
        System.out.println("  First 10: " + Arrays.toString(Arrays.copyOf(sorted, 10)) + "...\n");

        // Manual override
        System.out.println("Manual override - using BubbleSort on large array:");
        sorter.setStrategy(new BubbleSort());
        sorter.executeSort(large);
        System.out.println("  (Notice the performance difference!)\n");

        System.out.println("=== END OF DEMO ===");
    }
}
