import java.io.*;

// ==================== COFFEE EXAMPLE ====================

// Component Interface
interface Coffee {
    double getCost();
    String getDescription();
}

// Concrete Components
class SimpleCoffee implements Coffee {
    @Override
    public double getCost() { return 5.0; }

    @Override
    public String getDescription() { return "Simple Coffee"; }
}

class Espresso implements Coffee {
    @Override
    public double getCost() { return 8.0; }

    @Override
    public String getDescription() { return "Espresso"; }
}

// Base Decorator
abstract class CoffeeDecorator implements Coffee {
    protected Coffee decoratedCoffee;

    public CoffeeDecorator(Coffee coffee) {
        this.decoratedCoffee = coffee;
    }

    @Override
    public double getCost() { return decoratedCoffee.getCost(); }

    @Override
    public String getDescription() { return decoratedCoffee.getDescription(); }
}

// Concrete Decorators
class MilkDecorator extends CoffeeDecorator {
    public MilkDecorator(Coffee coffee) { super(coffee); }

    @Override
    public double getCost() { return super.getCost() + 1.5; }

    @Override
    public String getDescription() { return super.getDescription() + " + Milk"; }
}

class SugarDecorator extends CoffeeDecorator {
    public SugarDecorator(Coffee coffee) { super(coffee); }

    @Override
    public double getCost() { return super.getCost() + 0.5; }

    @Override
    public String getDescription() { return super.getDescription() + " + Sugar"; }
}

class WhippedCreamDecorator extends CoffeeDecorator {
    public WhippedCreamDecorator(Coffee coffee) { super(coffee); }

    @Override
    public double getCost() { return super.getCost() + 2.0; }

    @Override
    public String getDescription() { return super.getDescription() + " + Whipped Cream"; }
}

class CaramelDecorator extends CoffeeDecorator {
    public CaramelDecorator(Coffee coffee) { super(coffee); }

    @Override
    public double getCost() { return super.getCost() + 2.5; }

    @Override
    public String getDescription() { return super.getDescription() + " + Caramel"; }
}

// ==================== I/O STREAM EXAMPLE ====================

// Component Interface
interface DataStream {
    void write(String data) throws IOException;
    String read() throws IOException;
}

// Concrete Component
class FileDataStream implements DataStream {
    private String filename;

    public FileDataStream(String filename) {
        this.filename = filename;
    }

    @Override
    public void write(String data) throws IOException {
        try (FileWriter fw = new FileWriter(filename)) {
            fw.write(data);
        }
        System.out.println("  [FileDataStream] Wrote raw data to " + filename);
    }

    @Override
    public String read() throws IOException {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader br = new BufferedReader(new FileReader(filename))) {
            String line;
            while ((line = br.readLine()) != null) sb.append(line);
        }
        System.out.println("  [FileDataStream] Read raw data from " + filename);
        return sb.toString();
    }
}

// Base Decorator
abstract class DataStreamDecorator implements DataStream {
    protected DataStream wrappee;

    public DataStreamDecorator(DataStream stream) {
        this.wrappee = stream;
    }
}

// Encryption Decorator
class EncryptionDecorator extends DataStreamDecorator {
    public EncryptionDecorator(DataStream stream) { super(stream); }

    @Override
    public void write(String data) throws IOException {
        String encrypted = encrypt(data);
        System.out.println("  [EncryptionDecorator] Encrypting data...");
        wrappee.write(encrypted);
    }

    @Override
    public String read() throws IOException {
        String data = wrappee.read();
        System.out.println("  [EncryptionDecorator] Decrypting data...");
        return decrypt(data);
    }

    private String encrypt(String data) {
        // Simple Caesar cipher for demonstration
        StringBuilder sb = new StringBuilder();
        for (char c : data.toCharArray()) sb.append((char)(c + 3));
        return sb.toString();
    }

    private String decrypt(String data) {
        StringBuilder sb = new StringBuilder();
        for (char c : data.toCharArray()) sb.append((char)(c - 3));
        return sb.toString();
    }
}

// Compression Decorator
class CompressionDecorator extends DataStreamDecorator {
    public CompressionDecorator(DataStream stream) { super(stream); }

    @Override
    public void write(String data) throws IOException {
        String compressed = compress(data);
        System.out.println("  [CompressionDecorator] Compressing data (" + data.length() + " -> " + compressed.length() + " chars)");
        wrappee.write(compressed);
    }

    @Override
    public String read() throws IOException {
        String data = wrappee.read();
        System.out.println("  [CompressionDecorator] Decompressing data...");
        return decompress(data);
    }

    // Simplified RLE compression for demonstration
    private String compress(String data) {
        StringBuilder sb = new StringBuilder();
        int i = 0;
        while (i < data.length()) {
            char c = data.charAt(i);
            int count = 1;
            while (i + count < data.length() && data.charAt(i + count) == c) count++;
            sb.append(count).append(c);
            i += count;
        }
        return sb.toString();
    }

    private String decompress(String data) {
        StringBuilder sb = new StringBuilder();
        int i = 0;
        while (i < data.length()) {
            int numStart = i;
            while (i < data.length() && Character.isDigit(data.charAt(i))) i++;
            int count = Integer.parseInt(data.substring(numStart, i));
            if (i < data.length()) {
                char c = data.charAt(i);
                sb.append(String.valueOf(c).repeat(count));
                i++;
            }
        }
        return sb.toString();
    }
}

// ==================== MAIN ====================

public class DecoratorPattern {
    public static void main(String[] args) throws IOException {
        System.out.println("=== DECORATOR PATTERN - Coffee Shop Example ===\n");

        // Simple coffee
        Coffee coffee = new SimpleCoffee();
        System.out.println(coffee.getDescription() + " => $" + coffee.getCost());

        // Stack decorators
        coffee = new MilkDecorator(coffee);
        System.out.println(coffee.getDescription() + " => $" + coffee.getCost());

        coffee = new SugarDecorator(coffee);
        System.out.println(coffee.getDescription() + " => $" + coffee.getCost());

        coffee = new WhippedCreamDecorator(coffee);
        System.out.println(coffee.getDescription() + " => $" + coffee.getCost());

        System.out.println("\n--- Espresso with Caramel and Milk ---");
        Coffee espresso = new CaramelDecorator(new MilkDecorator(new Espresso()));
        System.out.println(espresso.getDescription() + " => $" + espresso.getCost());

        // I/O Stream Example
        System.out.println("\n=== DECORATOR PATTERN - I/O Stream Example ===\n");

        String tempFile = System.getProperty("java.io.tmpdir") + "/decorator_demo.txt";

        // Plain write
        System.out.println("1. Writing with Encryption + Compression decorators:");
        DataStream stream = new CompressionDecorator(
                                new EncryptionDecorator(
                                    new FileDataStream(tempFile)));
        stream.write("Hello Decorator Pattern!!!");

        System.out.println("\n2. Reading back with same decorator stack:");
        String result = stream.read();
        System.out.println("  Result: " + result);

        // Cleanup
        new File(tempFile).delete();
    }
}
