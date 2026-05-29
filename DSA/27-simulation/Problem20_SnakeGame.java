/**
 * Problem: Design Snake Game (LeetCode 353)
 * Approach: Deque for snake body, HashSet for O(1) collision detection
 * Complexity: O(1) per move
 * Production Analogy: Real-time entity tracking in game servers with collision detection
 */
import java.util.*;
public class Problem20_SnakeGame {
    int width, height, foodIdx, score;
    int[][] food;
    Deque<int[]> snake = new ArrayDeque<>();
    Set<String> body = new HashSet<>();

    public Problem20_SnakeGame(int w, int h, int[][] food) {
        this.width = w; this.height = h; this.food = food;
        snake.offer(new int[]{0,0}); body.add("0,0");
    }
    public int move(String direction) {
        int[] head = snake.peekFirst();
        int r = head[0], c = head[1];
        if (direction.equals("U")) r--; else if (direction.equals("D")) r++;
        else if (direction.equals("L")) c--; else c++;
        if (r<0||r>=height||c<0||c>=width) return -1;
        if (foodIdx < food.length && r==food[foodIdx][0] && c==food[foodIdx][1]) {
            foodIdx++; score++;
        } else {
            int[] tail = snake.pollLast();
            body.remove(tail[0]+","+tail[1]);
        }
        if (body.contains(r+","+c)) return -1;
        snake.offerFirst(new int[]{r,c});
        body.add(r+","+c);
        return score;
    }
    public static void main(String[] args) {
        Problem20_SnakeGame g = new Problem20_SnakeGame(3,2,new int[][]{{1,2},{0,1}});
        System.out.println(g.move("R")); // 0
        System.out.println(g.move("D")); // 0
        System.out.println(g.move("R")); // 1
    }
}
