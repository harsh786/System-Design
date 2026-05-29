/**
 * Problem: Elevator Simulation (SCAN algorithm)
 * Approach: Direction-based serving (elevator/SCAN disk scheduling)
 * Complexity: O(n log n) for sorting requests
 * Production Analogy: Disk I/O scheduling, elevator dispatch in smart buildings
 */
import java.util.*;
public class Problem46_ElevatorSimulation {
    int currentFloor = 0, direction = 1; // 1=up, -1=down
    TreeSet<Integer> upRequests = new TreeSet<>(), downRequests = new TreeSet<>();

    public void addRequest(int floor) {
        if (floor >= currentFloor) upRequests.add(floor);
        else downRequests.add(floor);
    }

    public List<Integer> serve() {
        List<Integer> order = new ArrayList<>();
        while (!upRequests.isEmpty() || !downRequests.isEmpty()) {
            if (direction == 1) {
                while (!upRequests.isEmpty()) { currentFloor = upRequests.pollFirst(); order.add(currentFloor); }
                direction = -1;
                // remaining requests that are below
                TreeSet<Integer> temp = new TreeSet<>(downRequests);
                downRequests.clear();
                downRequests.addAll(temp);
            } else {
                while (!downRequests.isEmpty()) { currentFloor = downRequests.pollLast(); order.add(currentFloor); }
                direction = 1;
            }
        }
        return order;
    }

    public static void main(String[] args) {
        Problem46_ElevatorSimulation elev = new Problem46_ElevatorSimulation();
        for (int f : new int[]{3, 7, 1, 8, 2, 5}) elev.addRequest(f);
        System.out.println("Serve order: " + elev.serve());
    }
}
