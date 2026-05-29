/**
 * Problem: Time Needed to Buy Tickets (LeetCode 2073)
 * Approach: Calculate contribution of each person
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Queue wait time estimation in service systems
 */
public class Problem31_TimeNeededToBuyTickets {
    public int timeRequiredToBuy(int[] tickets, int k) {
        int time = 0;
        for (int i = 0; i < tickets.length; i++) {
            time += Math.min(tickets[i], i <= k ? tickets[k] : tickets[k]-1);
        }
        return time;
    }
    public static void main(String[] args) {
        System.out.println(new Problem31_TimeNeededToBuyTickets().timeRequiredToBuy(new int[]{2,3,2}, 2)); // 6
    }
}
