public class Problem13_MedianTwoSortedArrays {
    static double findMedianSortedArrays(int[] a, int[] b) {
        if (a.length > b.length) return findMedianSortedArrays(b, a);
        int m = a.length, n = b.length, lo = 0, hi = m;
        while (lo <= hi) {
            int i = (lo + hi) / 2, j = (m + n + 1) / 2 - i;
            int lA = i == 0 ? Integer.MIN_VALUE : a[i-1];
            int rA = i == m ? Integer.MAX_VALUE : a[i];
            int lB = j == 0 ? Integer.MIN_VALUE : b[j-1];
            int rB = j == n ? Integer.MAX_VALUE : b[j];
            if (lA <= rB && lB <= rA) {
                if ((m + n) % 2 == 0) return (Math.max(lA, lB) + Math.min(rA, rB)) / 2.0;
                return Math.max(lA, lB);
            } else if (lA > rB) hi = i - 1;
            else lo = i + 1;
        }
        return 0;
    }
    
    public static void main(String[] args) {
        System.out.println(findMedianSortedArrays(new int[]{1, 3}, new int[]{2})); // 2.0
    }
}
