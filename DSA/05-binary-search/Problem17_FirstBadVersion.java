/**
 * Problem 17: First Bad Version
 * 
 * Versions 1..n, some point onwards all are bad. Find the first bad version.
 * 
 * Approach: Binary search for leftmost true in [false..false, true..true].
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Git bisect — finding the first commit that introduced
 * a regression in a linear commit history.
 */
public class Problem17_FirstBadVersion {
    private static int bad;

    private static boolean isBadVersion(int version) {
        return version >= bad;
    }

    public static int firstBadVersion(int n) {
        int lo = 1, hi = n;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (isBadVersion(mid)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    public static void main(String[] args) {
        bad = 4;
        System.out.println(firstBadVersion(5)); // 4
        bad = 1;
        System.out.println(firstBadVersion(1)); // 1
        bad = 1;
        System.out.println(firstBadVersion(3)); // 1
        bad = 1702766719;
        System.out.println(firstBadVersion(2126753390)); // 1702766719
    }
}
