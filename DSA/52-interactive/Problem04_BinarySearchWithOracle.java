import java.util.*;

public class Problem04_BinarySearchWithOracle {
    static int[] hiddenArray = {1, 3, 5, 7, 9, 11, 13};
    
    static int query(int index) { return hiddenArray[index]; }
    static int size() { return hiddenArray.length; }
    
    static int search(int target) {
        int lo = 0, hi = size() - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int val = query(mid);
            if (val == target) return mid;
            else if (val < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Search 7: index=" + search(7)); // 3
        System.out.println("Search 4: index=" + search(4)); // -1
    }
}
