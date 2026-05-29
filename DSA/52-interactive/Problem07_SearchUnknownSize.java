import java.util.*;

public class Problem07_SearchUnknownSize {
    // Search in Sorted Array of Unknown Size (LC 702)
    static int[] arr = {1,3,5,7,9,11,13,15,17,19};
    
    static int get(int index) {
        if (index >= arr.length) return Integer.MAX_VALUE;
        return arr[index];
    }
    
    static int search(int target) {
        int hi = 1;
        while (get(hi) < target) hi *= 2;
        int lo = hi / 2;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int val = get(mid);
            if (val == target) return mid;
            else if (val < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Search 9: " + search(9)); // 4
        System.out.println("Search 12: " + search(12)); // -1
    }
}
