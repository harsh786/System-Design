import java.util.*;

/**
 * Problem 13: Asteroid Collision (LeetCode 735)
 * 
 * Asteroids moving in a row. Positive = right, negative = left.
 * When they collide, smaller one explodes. Equal = both explode.
 * 
 * Monotonic Invariant: Stack maintains surviving asteroids. Collision happens
 * only when stack top is positive and incoming is negative.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Message queue collision resolution - conflicting events
 * cancel each other based on priority/magnitude.
 */
public class Problem13_AsteroidCollision {
    
    public int[] asteroidCollision(int[] asteroids) {
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int ast : asteroids) {
            boolean alive = true;
            while (alive && ast < 0 && !stack.isEmpty() && stack.peek() > 0) {
                if (stack.peek() < -ast) {
                    stack.pop();
                } else if (stack.peek() == -ast) {
                    stack.pop();
                    alive = false;
                } else {
                    alive = false;
                }
            }
            if (alive) stack.push(ast);
        }
        
        int[] result = new int[stack.size()];
        for (int i = result.length - 1; i >= 0; i--) result[i] = stack.pop();
        return result;
    }
    
    public static void main(String[] args) {
        Problem13_AsteroidCollision sol = new Problem13_AsteroidCollision();
        
        System.out.println(Arrays.toString(sol.asteroidCollision(new int[]{5,10,-5})));   // [5,10]
        System.out.println(Arrays.toString(sol.asteroidCollision(new int[]{8,-8})));      // []
        System.out.println(Arrays.toString(sol.asteroidCollision(new int[]{10,2,-5})));   // [10]
        System.out.println(Arrays.toString(sol.asteroidCollision(new int[]{-2,-1,1,2}))); // [-2,-1,1,2]
    }
}
