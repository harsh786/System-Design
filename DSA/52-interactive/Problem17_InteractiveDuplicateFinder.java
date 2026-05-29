import java.util.*;

public class Problem17_InteractiveDuplicateFinder {
    // Find duplicate with limited queries (Floyd's cycle detection concept)
    static int[] arr = {1, 3, 4, 2, 2};
    static int query(int i) { return arr[i]; }
    
    static int findDuplicate(int n) {
        int slow = query(0), fast = query(query(0));
        while (slow != fast) { slow = query(slow); fast = query(query(fast)); }
        slow = 0;
        while (slow != fast) { slow = query(slow); fast = query(fast); }
        return slow;
    }
    
    public static void main(String[] args) {
        System.out.println("Duplicate: " + findDuplicate(arr.length)); // 2
    }
}
