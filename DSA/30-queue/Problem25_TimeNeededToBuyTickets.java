import java.util.*;

public class Problem25_TimeNeededToBuyTickets {
    public static int timeRequiredToBuy(int[] tickets, int k) {
        int time = 0;
        for (int i = 0; i < tickets.length; i++) {
            time += Math.min(tickets[i], i <= k ? tickets[k] : tickets[k] - 1);
        }
        return time;
    }
    public static void main(String[] args) {
        System.out.println(timeRequiredToBuy(new int[]{2,3,2}, 2)); // 6
    }
}
