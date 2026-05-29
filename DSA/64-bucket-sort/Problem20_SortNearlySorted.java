import java.util.*;
public class Problem20_SortNearlySorted {
    /* Each element is at most k positions from sorted position - use min-heap of size k+1 */
    public void sortNearlySorted(int[] arr, int k) {
        PriorityQueue<Integer> pq=new PriorityQueue<>();
        int idx=0;
        for(int i=0;i<arr.length;i++){pq.offer(arr[i]);if(pq.size()>k) arr[idx++]=pq.poll();}
        while(!pq.isEmpty()) arr[idx++]=pq.poll();
    }
    public static void main(String[] args){ Problem20_SortNearlySorted s=new Problem20_SortNearlySorted(); int[] a={6,5,3,2,8,10,9}; s.sortNearlySorted(a,3); System.out.println(Arrays.toString(a)); }
}
