import java.util.*;

public class Problem11_CorporateFlightBookings {
    public int[] corpFlightBookings(int[][] bookings, int n) {
        int[] diff = new int[n + 1];
        for (int[] b : bookings) { diff[b[0] - 1] += b[2]; if (b[1] < n) diff[b[1]] -= b[2]; }
        int[] res = new int[n];
        res[0] = diff[0];
        for (int i = 1; i < n; i++) res[i] = res[i - 1] + diff[i];
        return res;
    }

    public static void main(String[] args) {
        Problem11_CorporateFlightBookings sol = new Problem11_CorporateFlightBookings();
        System.out.println(Arrays.toString(sol.corpFlightBookings(new int[][]{{1,2,10},{2,3,20},{2,5,25}}, 5)));
    }
}
