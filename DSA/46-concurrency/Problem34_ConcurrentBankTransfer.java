import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem34_ConcurrentBankTransfer {
    /**
     * Problem: Concurrent Bank Transfer (Deadlock avoidance)
     * Transfer between accounts without deadlock using lock ordering by account ID.
     * Time: O(1) | Space: O(accounts)
     * Production Analogy: Banking system transferring funds between accounts concurrently.
     */
    private final Map<Integer, Long> accounts = new ConcurrentHashMap<>();
    private final Map<Integer, ReentrantLock> locks = new ConcurrentHashMap<>();

    public void createAccount(int id, long balance) { accounts.put(id, balance); locks.put(id, new ReentrantLock()); }

    public boolean transfer(int from, int to, long amount) {
        int first = Math.min(from, to), second = Math.max(from, to);
        locks.get(first).lock(); locks.get(second).lock();
        try {
            if (accounts.get(from) < amount) return false;
            accounts.put(from, accounts.get(from) - amount);
            accounts.put(to, accounts.get(to) + amount);
            return true;
        } finally { locks.get(second).unlock(); locks.get(first).unlock(); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem34_ConcurrentBankTransfer bank = new Problem34_ConcurrentBankTransfer();
        bank.createAccount(1, 1000); bank.createAccount(2, 1000);
        Thread t1 = new Thread(() -> { for (int i = 0; i < 100; i++) bank.transfer(1, 2, 5); });
        Thread t2 = new Thread(() -> { for (int i = 0; i < 100; i++) bank.transfer(2, 1, 5); });
        t1.start(); t2.start(); t1.join(); t2.join();
        System.out.println("Account 1: " + bank.accounts.get(1) + ", Account 2: " + bank.accounts.get(2));
    }
}
