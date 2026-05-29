/**
 * Problem: Asteroid Collision (LeetCode 735)
 * Approach: Stack simulation - push right-movers, resolve collisions with left-movers
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Message conflict resolution in bidirectional queues
 */
import java.util.*;
public class Problem08_AsteroidCollision {
    public int[] asteroidCollision(int[] asteroids) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (int a : asteroids) {
            boolean alive = true;
            while (alive && a < 0 && !stack.isEmpty() && stack.peek() > 0) {
                if (stack.peek() < -a) stack.pop();
                else if (stack.peek() == -a) { stack.pop(); alive = false; }
                else alive = false;
            }
            if (alive) stack.push(a);
        }
        int[] res = new int[stack.size()];
        for (int i = res.length-1; i >= 0; i--) res[i] = stack.pop();
        return res;
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem08_AsteroidCollision().asteroidCollision(new int[]{5,10,-5}))); // [5,10]
    }
}
