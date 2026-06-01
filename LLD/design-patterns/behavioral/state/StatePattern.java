/**
 * State Design Pattern - Behavioral Pattern
 * 
 * Allows an object to alter its behavior when its internal state changes.
 * The object will appear to change its class.
 */

// ==================== EXAMPLE 1: VENDING MACHINE ====================

interface VendingMachineState {
    void insertCoin(VendingMachine machine);
    void selectProduct(VendingMachine machine);
    void dispense(VendingMachine machine);
}

class IdleState implements VendingMachineState {
    @Override
    public void insertCoin(VendingMachine machine) {
        System.out.println("Coin inserted. You can now select a product.");
        machine.setState(new HasCoinState());
    }

    @Override
    public void selectProduct(VendingMachine machine) {
        System.out.println("Please insert a coin first.");
    }

    @Override
    public void dispense(VendingMachine machine) {
        System.out.println("Please insert a coin and select a product first.");
    }
}

class HasCoinState implements VendingMachineState {
    @Override
    public void insertCoin(VendingMachine machine) {
        System.out.println("Coin already inserted. Please select a product.");
    }

    @Override
    public void selectProduct(VendingMachine machine) {
        if (machine.getStock() > 0) {
            System.out.println("Product selected. Dispensing...");
            machine.setState(new DispensingState());
            machine.dispense(); // trigger dispense immediately
        } else {
            System.out.println("Sorry, out of stock.");
            machine.setState(new OutOfStockState());
        }
    }

    @Override
    public void dispense(VendingMachine machine) {
        System.out.println("Please select a product first.");
    }
}

class DispensingState implements VendingMachineState {
    @Override
    public void insertCoin(VendingMachine machine) {
        System.out.println("Please wait, dispensing in progress.");
    }

    @Override
    public void selectProduct(VendingMachine machine) {
        System.out.println("Please wait, dispensing in progress.");
    }

    @Override
    public void dispense(VendingMachine machine) {
        machine.reduceStock();
        System.out.println("Product dispensed! Stock remaining: " + machine.getStock());
        if (machine.getStock() > 0) {
            machine.setState(new IdleState());
        } else {
            System.out.println("Machine is now out of stock.");
            machine.setState(new OutOfStockState());
        }
    }
}

class OutOfStockState implements VendingMachineState {
    @Override
    public void insertCoin(VendingMachine machine) {
        System.out.println("Sorry, machine is out of stock. Returning coin.");
    }

    @Override
    public void selectProduct(VendingMachine machine) {
        System.out.println("Sorry, machine is out of stock.");
    }

    @Override
    public void dispense(VendingMachine machine) {
        System.out.println("No product to dispense. Out of stock.");
    }
}

class VendingMachine {
    private VendingMachineState state;
    private int stock;

    public VendingMachine(int stock) {
        this.stock = stock;
        this.state = stock > 0 ? new IdleState() : new OutOfStockState();
    }

    public void setState(VendingMachineState state) { this.state = state; }
    public int getStock() { return stock; }
    public void reduceStock() { stock--; }

    public void insertCoin() { state.insertCoin(this); }
    public void selectProduct() { state.selectProduct(this); }
    public void dispense() { state.dispense(this); }
}

// ==================== EXAMPLE 2: ORDER LIFECYCLE ====================

interface OrderState {
    void next(Order order);
    void cancel(Order order);
    String getStatus();
}

class NewOrderState implements OrderState {
    @Override
    public void next(Order order) {
        System.out.println("Order is now being processed.");
        order.setState(new ProcessingOrderState());
    }

    @Override
    public void cancel(Order order) {
        System.out.println("Order cancelled.");
        order.setState(new CancelledOrderState());
    }

    @Override
    public String getStatus() { return "NEW"; }
}

class ProcessingOrderState implements OrderState {
    @Override
    public void next(Order order) {
        System.out.println("Order has been shipped.");
        order.setState(new ShippedOrderState());
    }

    @Override
    public void cancel(Order order) {
        System.out.println("Order cancelled during processing. Refund initiated.");
        order.setState(new CancelledOrderState());
    }

    @Override
    public String getStatus() { return "PROCESSING"; }
}

class ShippedOrderState implements OrderState {
    @Override
    public void next(Order order) {
        System.out.println("Order delivered successfully!");
        order.setState(new DeliveredOrderState());
    }

    @Override
    public void cancel(Order order) {
        System.out.println("Cannot cancel. Order already shipped.");
    }

    @Override
    public String getStatus() { return "SHIPPED"; }
}

class DeliveredOrderState implements OrderState {
    @Override
    public void next(Order order) {
        System.out.println("Order already delivered. No further transitions.");
    }

    @Override
    public void cancel(Order order) {
        System.out.println("Cannot cancel a delivered order. Please initiate a return.");
    }

    @Override
    public String getStatus() { return "DELIVERED"; }
}

class CancelledOrderState implements OrderState {
    @Override
    public void next(Order order) {
        System.out.println("Order is cancelled. No further transitions.");
    }

    @Override
    public void cancel(Order order) {
        System.out.println("Order is already cancelled.");
    }

    @Override
    public String getStatus() { return "CANCELLED"; }
}

class Order {
    private OrderState state;
    private String orderId;

    public Order(String orderId) {
        this.orderId = orderId;
        this.state = new NewOrderState();
    }

    public void setState(OrderState state) { this.state = state; }
    public void next() { state.next(this); }
    public void cancel() { state.cancel(this); }
    public String getStatus() { return state.getStatus(); }
    public String getOrderId() { return orderId; }
}

// ==================== MAIN ====================

public class StatePattern {
    public static void main(String[] args) {
        System.out.println("========== VENDING MACHINE EXAMPLE ==========\n");

        VendingMachine vm = new VendingMachine(2);

        // Normal flow
        System.out.println("--- Normal purchase flow ---");
        vm.insertCoin();
        vm.selectProduct();

        System.out.println("\n--- Invalid operations ---");
        vm.dispense();          // idle state, no coin
        vm.selectProduct();     // idle state, no coin

        System.out.println("\n--- Second purchase (last item) ---");
        vm.insertCoin();
        vm.selectProduct();

        System.out.println("\n--- Try purchasing when out of stock ---");
        vm.insertCoin();

        System.out.println("\n\n========== ORDER LIFECYCLE EXAMPLE ==========\n");

        // Normal order flow
        Order order1 = new Order("ORD-001");
        System.out.println("--- Order 1: Normal lifecycle ---");
        System.out.println("Status: " + order1.getStatus());
        order1.next();  // NEW -> PROCESSING
        order1.next();  // PROCESSING -> SHIPPED
        order1.next();  // SHIPPED -> DELIVERED
        order1.next();  // DELIVERED -> no transition
        System.out.println("Final status: " + order1.getStatus());

        System.out.println("\n--- Order 2: Cancelled during processing ---");
        Order order2 = new Order("ORD-002");
        order2.next();    // NEW -> PROCESSING
        order2.cancel();  // PROCESSING -> CANCELLED
        order2.next();    // CANCELLED -> no transition
        System.out.println("Final status: " + order2.getStatus());

        System.out.println("\n--- Order 3: Try to cancel after shipping ---");
        Order order3 = new Order("ORD-003");
        order3.next();    // NEW -> PROCESSING
        order3.next();    // PROCESSING -> SHIPPED
        order3.cancel();  // SHIPPED -> cannot cancel
        System.out.println("Final status: " + order3.getStatus());
    }
}
