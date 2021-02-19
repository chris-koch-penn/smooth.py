import os
import math
import collections
import json
import shutil

from . import utils

'''
A cascaded mini mapping is made as follows:
    - First generated a non-cascaded pretty map
    - After that have the minifier generate a shrink map and load that
    - After that cascade the two to obtain the mini map and save that
'''

# Tools to embed source map info in target code

lineNrLength = 6
maxNrOfSourceLinesPerModule = 1000000

# Tools to encode and decode numbers as base 64 variable length quantities


class Base64VlqConverter:
    def __init__(self):
        # Forward lookup table, from index to character, 64 symbols in total
        self.encoding = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        # Enable reverse lookup, so from character to index
        self.decoding = dict((char, i) for i, char in enumerate(self.encoding))

        # The 256 most used vlq's are prefabricated
        self.prefabSize = 256
        self.prefab = [self.encode([i], True) for i in range(self.prefabSize)]

    def encode(self, numbers, init=False):
        segment = ''
        for number in numbers:
            if not init and 0 < number < self.prefabSize:
                field = self.prefab[number]
            else:
                # Convert to binary, chop off '0b' and append sign bit
                signed = bin(abs(number))[2:] + ('1' if number < 0 else '0')
                # Determine minimum nr of needed 5 bit chunks (2 ^ 5 == 32)
                nChunks = math.ceil(len(signed) / 5.0)
                # Pad by prepending zeroes to fit integer nr of chunks
                padded = (5 * '0' + signed)[-nChunks * 5:]
                chunks = [
                    ('1' if iChunk else '0') + padded[                                     # Prefix first chunk with 0, continuation chunks with 1 (continuation bit)
                        # Pick out a not yet prefixed chunk from the padded bits
                        iChunk * 5: (iChunk + 1) * 5
                    ]
                    # Reverse chunks, so the chunk starting with 0 will be last, first has sign bit
                    for iChunk in range(nChunks - 1, -1, -1)
                ]                                                                           # So encountering a chunk with int value < 32 will denote end of number
                # Convert each chunk, incl. continuation bit to its encoding
                field = ''.join([self.encoding[int(chunk, 2)]
                                 for chunk in chunks])
            segment += field
        return segment

    def decode(self, segment):
        numbers = []
        accu = 0
        weight = 1

        for char in segment:
            ordinal = self.decoding[char]
            isContinuation = ordinal >= 32

            if isContinuation:
                # Reset continuation bit
                ordinal -= 32

            # It was the tail of a number
            if weight == 1:
                # Remember sign
                sign = -1 if ordinal % 2 else 1
                # Remove sign bit, no matter what it was
                ordinal //= 2

            # Add new ordinal as currently least significant
            accu += weight * ordinal

            if isContinuation:                                                              # If it's a continuation
                if weight == 1:  # If it's the first continuation it will have the sign bit
                    weight = 16  # So next weight is 16
                else:  # Else it won't have the sign bit:
                    weight *= 32  # So next weight * 32
            # Else  ('no continuation' means 'end of number', since chunks are reversed)
            else:
                # Append accumulated number to results
                numbers.append(sign * accu)
                accu = 0  # Reset accumulator for next number
                weight = 1  # Reset weight, next number will again start with least significant part

        return numbers


base64VlqConverter = Base64VlqConverter()

# Tools to create and combine sourcemaps

mapVersion = 3
iTargetLine, iTargetColumn, iSourceIndex, iSourceLine, iSourceColumn = range(
    5)    # Line indexes rather than line numbers are stored


class SourceMapper:  # There's only one sourcemapper needed to generate all maps of a module
    def __init__(
        self,
        moduleName,
        targetDir,
        minify,
        dump
    ):
        self.moduleName = moduleName
        self.targetDir = targetDir
        self.minify = minify
        self.dump = dump

    def generateAndSavePrettyMap(self, sourceLineNrs):
        self.prettyMappings = [[targetLineIndex, 0, 0, sourceLineNr - 1, 0]
                               for targetLineIndex, sourceLineNr in enumerate(sourceLineNrs)]
        self.prettyMappings.sort()

        infix = '.pretty' if self.minify else ''

        self.save(self.prettyMappings, infix)

        if self.dump:
            self.dumpMap(self.prettyMappings, infix, '.py')
            self.dumpDeltaMap(self.prettyMappings, infix)

    def cascadeAndSaveMiniMap(self):
        # N.B. self.prettyMappings has to be sorted in advance
        def getCascadedMapping(shrinkMapping):
            prettyMapping = self.prettyMappings[min(
                shrinkMapping[iSourceLine], len(self.prettyMappings) - 1)]

            result = (
                # Target location from shrink mapping
                shrinkMapping[: iTargetColumn + 1]
                +
                # Source location from self
                prettyMapping[iSourceIndex:]
            )
            if self.dump:
                self.cascadeMapdumpFile.write('{} {} {}\n'.format(
                    result, shrinkMapping, prettyMapping))
            return result

        if self.dump:
            self.cascadeMapdumpFile = utils.create(
                f'{self.targetDir}/{self.moduleName}.cascade_map_dump')

        self.miniMappings = [
            getCascadedMapping(shrinkMapping)
            for shrinkMapping in self.shrinkMappings
        ]
        self.miniMappings.sort()

        self.save(self.miniMappings, '')

        if self.dump:
            self.cascadeMapdumpFile.close()

    def loadShrinkMap(self):
        with open(f'{self.targetDir}/{self.moduleName}.shrink.map') as mapFile:
            rawMap = json.loads(mapFile.read())

        deltaMappings = [
            [base64VlqConverter.decode(segment)
             for segment in group.split(',')]
            for group in rawMap['mappings'] .split(';')
        ]

        '''
        Fields in a delta segment as directly decoded from the output of the minifier:
          index (target line index implicit, is group index)
            0: target column index
            1: source file index        (optional)      (always zero)
            2: source line index        (optional)
            3: source column index      (optional)
            4: name index               (optional)
            
        Fields in a shrinkMapping:
          index
            0: target line index (is group index, a group represents a target line)
            1: target column index
            2: source file index        (always zero)   (i = 1)
            3: source line index                        (i = 2)
            4: source column index                      (i = 3)
            5: source name index        (left out)
        '''

        self.shrinkMappings = []
        for groupIndex, deltaGroup in enumerate(deltaMappings):
            for segmentIndex, deltaSegment in enumerate(deltaGroup):
                # Shrink map ends with empty group, i.e. 'holding empty segment'
                if deltaSegment:
                    if segmentIndex:
                        self.shrinkMappings.append(
                            [groupIndex, deltaSegment[0] + self.shrinkMappings[-1][1]])
                    else:                                                           # Start of group
                        # Absolute target column
                        self.shrinkMappings.append(
                            [groupIndex, deltaSegment[0]])

                    # So i in [1, 2, 3]
                    for i in range(1, 4):
                        if groupIndex or segmentIndex:
                            self.shrinkMappings[-1] .append(
                                deltaSegment[i] + self.shrinkMappings[-2][i + 1])
                        else:                                                       # Start of map
                            try:
                                # Absolut file index, source line and source column
                                self.shrinkMappings[-1] .append(
                                    deltaSegment[i])
                            except:                                                 # Shrink map starts with 'A' rather than 'AAAA'
                                self.shrinkMappings[-1] .append(0)
        self.shrinkMappings.sort()  # Sort on target line and inside that on target column

        if self.dump:
            self.dumpMap(self.shrinkMappings, '.shrink', '.py')
            self.dumpDeltaMap(deltaMappings, '.shrink')

    def save(self, mappings, infix):
        deltaMappings = []
        oldMapping = [-1, 0, 0, 0, 0]
        for mapping in mappings:
            newGroup = mapping[iTargetLine] != oldMapping[iTargetLine]

            if newGroup:
                # Append new group
                deltaMappings.append([])

            # Append new segment, one for each mapping
            deltaMappings[-1] .append([])

            if newGroup:
                # Only target column reset for every group
                deltaMappings[-1][-1] .append(mapping[iTargetColumn])
            else:
                # Others are delta's, so cumulative
                deltaMappings[-1][-1] .append(mapping[iTargetColumn] -
                                              oldMapping[iTargetColumn])

            for i in [iSourceIndex, iSourceLine, iSourceColumn]:
                deltaMappings[-1][-1] .append(mapping[i] - oldMapping[i])

            oldMapping = mapping

        rawMap = collections.OrderedDict([
            ('version', mapVersion),
            ('file', f'{self.moduleName}.js'),  # Target
            ('sources', [f'{self.moduleName}{infix}.py']),
            # ('sourcesContent', [None]),
            ('mappings', ';'.join([
                ','.join([
                    base64VlqConverter.encode(segment)
                    for segment in group
                ])
                for group in deltaMappings
            ]))
        ])

        with utils.create(f'{self.targetDir}/{self.moduleName}{infix}.map') as mapFile:
            mapFile.write(json.dumps(rawMap, indent='\t'))

        if self.dump:
            self.dumpMap(mappings, infix, '.py')
            self.dumpDeltaMap(deltaMappings, infix)

    def dumpMap(self, mappings, infix, sourceExtension):
        with utils.create(f'{self.targetDir}/{self.moduleName}{infix}.map_dump') as mapdumpFile:
            mapdumpFile.write(f'mapVersion: {mapVersion}\n\n')
            mapdumpFile.write(f'targetPath: {self.moduleName}.js\n\n')
            mapdumpFile.write(
                f'sourcePath: {self.moduleName}{infix}{sourceExtension}\n\n')
            mapdumpFile.write('mappings:\n')
            for mapping in mappings:
                mapdumpFile.write('\t{}\n'.format(mapping))

    def dumpDeltaMap(self, deltaMappings, infix):
        with utils.create(f'{self.targetDir}/{self.moduleName}{infix}.delta_map_dump') as deltaMapdumpFile:
            for group in deltaMappings:
                deltaMapdumpFile.write('(New group) ')
                for segment in group:
                    deltaMapdumpFile.write('Segment: {}\n'.format(segment))

    def generateMultilevelMap(self):
        # !!!     , 'self.mapPath')
        utils.log(False, 'Saving multi-level sourcemap in: {}\n')
        self.loadShrinkMap()
        self.cascadeAndSaveMiniMap()
