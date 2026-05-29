import java.util.*;

/**
 * Problem 35: Design Phone Directory
 * 
 * API Contract:
 * - get(): Provide an available number. Return -1 if none.
 * - check(number): Check if number is available.
 * - release(number): Release number back.
 * 
 * Complexity: O(1) for all operations
 * Data Structure: HashSet of available numbers + Queue for O(1) get
 * 
 * Production Analogy: Port allocation, IP address pool (DHCP),
 * connection ID assignment, ticket number generation
 */
public class Problem35_DesignPhoneDirectory {

    static class PhoneDirectory {
        private Set<Integer> available;
        private Queue<Integer> queue;

        public PhoneDirectory(int maxNumbers) {
            available = new HashSet<>();
            queue = new LinkedList<>();
            for (int i = 0; i < maxNumbers; i++) {
                available.add(i);
                queue.offer(i);
            }
        }

        public int get() {
            if (queue.isEmpty()) return -1;
            int num = queue.poll();
            available.remove(num);
            return num;
        }

        public boolean check(int number) {
            return available.contains(number);
        }

        public void release(int number) {
            if (!available.contains(number)) {
                available.add(number);
                queue.offer(number);
            }
        }
    }

    public static void main(String[] args) {
        PhoneDirectory dir = new PhoneDirectory(3);
        assert dir.get() == 0;
        assert dir.get() == 1;
        assert dir.check(2);
        assert dir.get() == 2;
        assert !dir.check(2);
        dir.release(2);
        assert dir.check(2);
        assert dir.get() == 2;
        assert dir.get() == -1; // all taken

        System.out.println("All tests passed!");
    }
}
