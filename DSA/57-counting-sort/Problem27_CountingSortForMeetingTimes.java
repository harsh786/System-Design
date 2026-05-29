import java.util.*;

public class Problem27_CountingSortForMeetingTimes {
    // Sort meeting start times (0-1439 minutes in a day)
    public static int[] sortMeetings(int[] startTimes) {
        int[] count = new int[1440];
        for (int t : startTimes) count[t]++;
        int idx = 0;
        for (int i = 0; i < 1440; i++) while (count[i]-- > 0) startTimes[idx++] = i;
        return startTimes;
    }

    public static void main(String[] args) {
        int[] times = {540, 480, 600, 540, 720, 480};
        System.out.println(Arrays.toString(sortMeetings(times)));
    }
}
