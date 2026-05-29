import java.util.*;

public class Problem13_MinimumPlatforms {
    public int findPlatform(int[] arr, int[] dep) {
        Arrays.sort(arr); Arrays.sort(dep);
        int plat = 0, max = 0, i = 0, j = 0;
        while (i < arr.length) {
            if (arr[i] <= dep[j]) { plat++; i++; }
            else { plat--; j++; }
            max = Math.max(max, plat);
        }
        return max;
    }

    public static void main(String[] args) {
        Problem13_MinimumPlatforms sol = new Problem13_MinimumPlatforms();
        System.out.println(sol.findPlatform(new int[]{900,940,950,1100,1500,1800}, new int[]{910,1200,1120,1130,1900,2000})); // 3
    }
}
