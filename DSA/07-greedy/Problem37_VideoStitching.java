/**
 * Problem 37: Video Stitching (LeetCode 1024)
 *
 * Greedy Choice: Like Jump Game II - at each point, choose clip that extends farthest.
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Minimum number of log segments to cover a complete time window.
 */
import java.util.*;
public class Problem37_VideoStitching {
    
    public static int videoStitching(int[][] clips, int time) {
        Arrays.sort(clips, (a, b) -> a[0] != b[0] ? a[0] - b[0] : b[1] - a[1]);
        int count = 0, end = 0, farthest = 0, i = 0;
        while (end < time) {
            while (i < clips.length && clips[i][0] <= end)
                farthest = Math.max(farthest, clips[i++][1]);
            if (farthest == end) return -1;
            end = farthest;
            count++;
        }
        return count;
    }
    
    public static void main(String[] args) {
        System.out.println(videoStitching(new int[][]{{0,2},{4,6},{8,10},{1,9},{1,5},{5,9}}, 10)); // 3
        System.out.println(videoStitching(new int[][]{{0,1},{1,2}}, 5)); // -1
        System.out.println(videoStitching(new int[][]{{0,4},{2,8}}, 5)); // 2
    }
}
