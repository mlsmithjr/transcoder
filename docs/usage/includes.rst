==============
Using includes
==============

This feature requires a deeper familiarity with the YAML format. Essentially, you can define a partial profile or a full one and later "include" it into another profile. This facilitates reuse of definitions and simpler profiles.
All options from all sections of the profile are combined.  If there is a conflict, the descendant one wins.
Profile sections input_options and output_options are combined.  So all included profile options are combined with the descendant.
Since the introduction of mixins you should only put general, non-encoding options in output_options.  Audio, video, and subtitle options have their own sections now (see Mixins before proceeding).
The rule is: input_options and output_options can be built-up via includes (inheritance), but mixins are replacements and the last most recent one wins.


.. code-block:: yaml

    #
    # Merge-style example
    #
    profiles:
        # values universal to all my high-quality transcodes
        hq:
          output_options:  # options using hyphens and separate lines are "lists"
            - "-crf 18"
            - "-preset slow"
            - "-c:a copy"
            - "-c:s copy"
            - "-f matroska"
          threshold: 20
          extension: ".mkv"

        hevc_cuda:
          include: hq     # pull in everything defined above in "hq"
          output_options: # combine these options with those from "hq"
            - "-c:v hevc_nvenc"
            - "-profile:v main"
          threshold: 18    # replace "hq" threshold value with 18


The above example is equivalent to:

.. code-block:: yaml

      hevc_cuda:
        output_options:
          - "-crf 18"
          - "-preset slow"
          - "-c:a copy"
          - "-c:s copy"
          - "-f matroska"
          - "-c:v hevc_nvenc"
          - "-profile:v main"
        threshold : 18
        extension: ".mkv"

The advantage is that now we have a base (parent) profile we can include into many others to avoid repetitive profile definitions.  And, if we decide to change our base threshold, for example, we only need to change it in the base (parent).

Note that the profiles "hq" and "hevc_cuda" were combined, and the value for threshold was overridden to 18.
Lets refer to the first (base) profile as the parent, and the second as the child. So a child profile can include one or more parent profiles.  All values in the child are retained. However, if input_options or output_options are lists instead of strings, the parent and child values will be combined.
Here is the same example slightly reformatted:

.. code-block:: yaml

    #
    # Replace-style example
    #
      profiles:
        hq:
          output_options:
            - "-crf 18"
            - "-preset slow"
            - "-c:a copy"
            - "-c:s copy"
            - "-f matroska"
          threshold: 20
          extension: ".mkv"

        hevc_cuda:
          include: hq
          output_options:
            - "-c:v hevc_nvenc"
            - "-profile:v main"
          threshold: 18

This will produce a bad profile. Now I need to mention a feature of YAML only used in the **include** examples - lists.  YAML-formatted data can be very complex but pytranscoder requirements are meager and simple.  But to support the include feature in both _replace_ and _merge_ modes I needed another way to express input and output options.
Note the difference in the Merge and Replace examples is that Merge uses hyphens and a separate line for the output_options sections.  In Replace, all the options are on a single line.  The former is an expression of a "list of arguments".  The latter is just a "string of arguments" When a parent and child both have input_options or output_options that are lists, the two are combined.  If either is not a list (just a string), then the child wins and the parent version is ignored.
With this new information we can now see why the Replace example produces a bad profile.  It will look like this:

.. code-block:: yaml

    hevc_cuda:
      output_options:
        - "-c:v hevc_nvenc"
        - "-profile:v main"
      threshold: 18
      extension: ".mkv"

Since _output_options_ is a simple string rather than list, pytranscoder doesn't know how to merge them so it doesn't try.  The child values always wins.  So this profile will produce undesirable results because the parent options weren't merged.  Convert both back to lists and it will work again.
