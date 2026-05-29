import java.util.*;

/**
 * Problem 38: Battleships in a Board
 * 
 * Count battleships (horizontal or vertical 1xN blocks of 'X') in one pass, O(1) space.
 *
 * Approach: Count cells that are 'X' with no 'X' above or to the left (i.e., top-left corners).
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Counting distinct horizontal/vertical resource allocations in a
 * rack layout without traversing each allocation fully.
 */
public class Problem38_BattleshipsInABoard {

    public static int countBattleships(char[][] board) {
        int count = 0;
        for (int i = 0; i < board.length; i++)
            for (int j = 0; j < board[0].length; j++)
                if (board[i][j] == 'X'
                    && (i == 0 || board[i-1][j] != 'X')
                    && (j == 0 || board[i][j-1] != 'X'))
                    count++;
        return count;
    }

    public static void main(String[] args) {
        char[][] b = {{'X','.','.','X'},{'.','.','.','X'},{'.','.','.','X'}};
        System.out.println("Test 1: " + countBattleships(b)); // 2
        char[][] b2 = {{'.'}}; 
        System.out.println("Test 2: " + countBattleships(b2)); // 0
    }
}
