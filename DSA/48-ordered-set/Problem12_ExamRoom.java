import java.util.*;

public class Problem12_ExamRoom {
    // LC 855: Maximize distance to closest person when seating
    int n;
    TreeSet<Integer> seats;

    public Problem12_ExamRoom(int n) {
        this.n = n;
        seats = new TreeSet<>();
    }

    public int seat() {
        int pos = 0;
        if (!seats.isEmpty()) {
            int maxDist = seats.first(); // distance from 0 to first seat
            pos = 0;
            Integer prev = null;
            for (int s : seats) {
                if (prev != null) {
                    int dist = (s - prev) / 2;
                    if (dist > maxDist) { maxDist = dist; pos = prev + dist; }
                }
                prev = s;
            }
            if (n - 1 - seats.last() > maxDist) pos = n - 1;
        }
        seats.add(pos);
        return pos;
    }

    public void leave(int p) { seats.remove(p); }

    public static void main(String[] args) {
        Problem12_ExamRoom room = new Problem12_ExamRoom(10);
        System.out.println(room.seat()); // 0
        System.out.println(room.seat()); // 9
        System.out.println(room.seat()); // 4
        System.out.println(room.seat()); // 2
        room.leave(4);
        System.out.println(room.seat()); // 5
    }
}
