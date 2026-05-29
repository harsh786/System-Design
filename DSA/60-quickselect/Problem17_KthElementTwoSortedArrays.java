import java.util.*;

public class Problem17_KthElementTwoSortedArrays {
    /*
     * Kth Element of Two Sorted Arrays - Binary search approach
     * Time: O(log(min(m,n)))
     */
    public int kthElement(int[] a, int[] b, int k) {
        if (a.length > b.length) return kthElement(b, a, k);
        int n = a.length, m = b.length;
        int lo = Math.max(0, k - m), hi = Math.min(k, n);
        while (lo <= hi) {
            int cutA = (lo + hi) / 2;
            int cutB = k - cutA;
            int leftA = cutA == 0 ? Integer.MIN_VALUE : a[cutA - 1];
            int leftB = cutB == 0 ? Integer.MIN_VALUE : b[cutB - 1];
            int rightA = cutA == n ? Integer.MAX_VALUE : a[cutA];
            int rightB = cutB == m ? Integer.MAX_VALUE : b[cutB];
            if (leftA <= rightB && leftB <= rightA) return Math.max(leftA, leftB);
            else if (leftA > rightB) hi = cutA - 1;
            else lo = cutA + 1;
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem17_KthElementTwoSortedArrays sol = new Problem17_KthElementTwoSortedArrays();
        System.out.println(sol.kthElement(new int[]{2,3,6,7,9}, new int[]{1,4,8,10}, 5)); // 6
    }
}
