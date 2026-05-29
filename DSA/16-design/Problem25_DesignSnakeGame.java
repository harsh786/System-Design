import java.util.*;

/**
 * Problem 25: Design Snake Game
 * 
 * API Contract:
 * - move(direction): Move snake in direction ("U","D","L","R").
 *   Return score or -1 if game over.
 * 
 * Complexity: O(1) per move (with HashSet for body lookup)
 * Data Structure: Deque for snake body + HashSet for O(1) collision check
 * 
 * Production Analogy: Game state management, real-time simulation,
 * entity collision detection systems
 */
public class Problem25_DesignSnakeGame {

    static class SnakeGame {
        private int width, height, foodIndex, score;
        private int[][] food;
        private Deque<int[]> snake;
        private Set<String> body;

        public SnakeGame(int width, int height, int[][] food) {
            this.width = width;
            this.height = height;
            this.food = food;
            foodIndex = 0; score = 0;
            snake = new ArrayDeque<>();
            body = new HashSet<>();
            snake.offerFirst(new int[]{0, 0});
            body.add("0,0");
        }

        public int move(String direction) {
            int[] head = snake.peekFirst();
            int r = head[0], c = head[1];
            switch (direction) {
                case "U": r--; break;
                case "D": r++; break;
                case "L": c--; break;
                case "R": c++; break;
            }
            // Check wall collision
            if (r < 0 || r >= height || c < 0 || c >= width) return -1;

            // Check if eating food
            if (foodIndex < food.length && r == food[foodIndex][0] && c == food[foodIndex][1]) {
                foodIndex++;
                score++;
            } else {
                // Remove tail
                int[] tail = snake.pollLast();
                body.remove(tail[0] + "," + tail[1]);
            }

            // Check self collision (after removing tail)
            if (body.contains(r + "," + c)) return -1;

            snake.offerFirst(new int[]{r, c});
            body.add(r + "," + c);
            return score;
        }
    }

    public static void main(String[] args) {
        // 3x2 grid, food at (1,2),(0,1)
        SnakeGame game = new SnakeGame(3, 2, new int[][]{{1, 2}, {0, 1}});
        assert game.move("R") == 0;
        assert game.move("D") == 0;
        assert game.move("R") == 1; // ate food at (1,2)
        assert game.move("U") == 1;
        assert game.move("L") == 2; // ate food at (0,1)

        // Game over: wall
        SnakeGame g2 = new SnakeGame(2, 2, new int[][]{});
        assert g2.move("U") == -1;

        System.out.println("All tests passed!");
    }
}
