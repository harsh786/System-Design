import java.util.*;

/**
 * Problem 8: Asteroid Collision (LeetCode 735)
 * 
 * Asteroids moving in a row. Positive = right, negative = left.
 * When two collide, smaller one explodes. Equal = both explode. Same direction = no collision.
 * 
 * Approach: Stack-based simulation. Push positive asteroids. For negative ones,
 * pop smaller positives until empty/larger found or equal destroys both.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like conflict resolution in distributed systems - when two
 * competing writes arrive, the "larger" (higher priority/timestamp) wins.
 */
public class Problem08_AsteroidCollision {

    public static int[] asteroidCollision(int[] asteroids) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (int a : asteroids) {
            boolean alive = true;
            while (alive && a < 0 && !stack.isEmpty() && stack.peek() > 0) {
                if (stack.peek() < -a) {
                    stack.pop();
                } else if (stack.peek() == -a) {
                    stack.pop();
                    alive = false;
                } else {
                    alive = false;
                }
            }
            if (alive) stack.push(a);
        }
        int[] result = new int[stack.size()];
        for (int i = result.length - 1; i >= 0; i--) result[i] = stack.pop();
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(asteroidCollision(new int[]{5,10,-5})));  // [5,10]
        System.out.println(Arrays.toString(asteroidCollision(new int[]{8,-8})));     // []
        System.out.println(Arrays.toString(asteroidCollision(new int[]{10,2,-5})));  // [10]
        System.out.println(Arrays.toString(asteroidCollision(new int[]{-2,-1,1,2}))); // [-2,-1,1,2]
    }
}
