import java.util.*;
public class Problem30_BucketSortScoreRanges {
    public int[][] sortStudentsByScore(int[][] students) { // [id, score 0-100]
        List<int[]>[] buckets=new List[101]; for(int i=0;i<101;i++) buckets[i]=new ArrayList<>();
        for(int[] s:students) buckets[s[1]].add(s);
        int idx=students.length-1; for(int i=0;i<101;i++) for(int[] s:buckets[i]) students[idx--]=s;
        return students;
    }
    public static void main(String[] args){ int[][] s={{1,85},{2,92},{3,78},{4,92},{5,65}}; new Problem30_BucketSortScoreRanges().sortStudentsByScore(s); for(int[] st:s) System.out.println(Arrays.toString(st)); }
}
