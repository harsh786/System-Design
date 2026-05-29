/**
 * Problem: Vending Machine State Machine
 * Approach: State pattern with transitions based on events
 * Complexity: O(1) per transition
 * Production Analogy: Finite state machines in payment processing, order workflows
 */
public class Problem47_VendingMachineStateMachine {
    enum State { IDLE, COIN_INSERTED, ITEM_SELECTED, DISPENSING }
    State state = State.IDLE;
    int balance = 0;

    public String insertCoin(int amount) {
        if (state == State.IDLE || state == State.COIN_INSERTED) {
            balance += amount; state = State.COIN_INSERTED;
            return "Balance: " + balance;
        }
        return "Cannot insert coin in state: " + state;
    }

    public String selectItem(int price) {
        if (state != State.COIN_INSERTED) return "Insert coin first";
        if (balance < price) return "Insufficient balance. Need " + (price - balance) + " more";
        state = State.ITEM_SELECTED;
        return dispense(price);
    }

    private String dispense(int price) {
        state = State.DISPENSING;
        balance -= price;
        String result = "Dispensed! Change: " + balance;
        balance = 0; state = State.IDLE;
        return result;
    }

    public static void main(String[] args) {
        Problem47_VendingMachineStateMachine vm = new Problem47_VendingMachineStateMachine();
        System.out.println(vm.insertCoin(50));
        System.out.println(vm.insertCoin(50));
        System.out.println(vm.selectItem(75));
    }
}
