/**
 * Problem: Watering Plants (LeetCode 2079)
 * Approach: Linear simulation with refill trips
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Resource replenishment scheduling in delivery routing
 */
public class Problem38_WateringPlants {
    public int wateringPlants(int[] plants, int capacity) {
        int steps = 0, water = capacity;
        for (int i = 0; i < plants.length; i++) {
            if (water >= plants[i]) { water -= plants[i]; steps++; }
            else { steps += 2*i + 1; water = capacity - plants[i]; }
        }
        return steps;
    }
    public static void main(String[] args) {
        System.out.println(new Problem38_WateringPlants().wateringPlants(new int[]{2,2,3,3}, 5)); // 14
    }
}
